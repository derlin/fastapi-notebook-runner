import logging
from typing import Optional

import celery.states
from celery.result import AsyncResult
from cockpit_fastapi.worker import run_celery_task, get_celery_task_status, revoke_celery_task, REDIS_URL
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from redis import Redis
from redis.lock import Lock as RedisLock

app = FastAPI()

redis_instance = Redis.from_url(url=REDIS_URL)
celery_lock = RedisLock(redis_instance, name='task_lock')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

REDIS_TASK_ID_KEY = "current_task_id"


@app.get("/start")
def api_start():
    if not celery_lock.acquire(blocking_timeout=3):  # timeout in seconds
        raise HTTPException(status_code=401, detail="Could not acquire lock")
    try:
        if (current_task := _get_task_status()) is not None and not current_task.ready():
            raise HTTPException(status_code=401, detail=f"Another task is already running: {current_task.task_id}")
        task = run_celery_task.delay()
        redis_instance.set(REDIS_TASK_ID_KEY, task.task_id)
        return {"task_id": task.task_id}
    finally:
        celery_lock.release()


@app.get("/progress")
def api_progress(task_id: Optional[str] = None):
    task_status = _task_status_or_http_error(task_id)
    return _task_status_to_json(task_status)


@app.get("/error", response_class=PlainTextResponse)
def api_error(task_id: Optional[str] = None):
    task_status = _task_status_or_http_error(task_id)
    if task_status.status == celery.states.FAILURE:
        return str(task_status.traceback)
    return ""


@app.get("/output", response_class=PlainTextResponse)
def api_output(task_id: Optional[str] = None):
    task_status = _task_status_or_http_error(task_id)
    if task_status.status == celery.states.FAILURE:
        return str(task_status.traceback)
    return task_status.output


@app.get("/kill")
def api_kill(task_id: Optional[str] = None):
    task_status = _task_status_or_http_error(task_id)
    revoke_celery_task(task_status.task_id)
    return _task_status_to_json(task_status)


def _task_status_to_json(task_result: AsyncResult):
    return {
        "id": task_result.task_id,
        "status": task_result.status,
        "date": task_result.date_done,
    }


def _task_status_or_http_error(task_id: Optional[str]) -> AsyncResult:
    if task_id is not None:
        if (status := get_celery_task_status(task_id)) is not None:
            return status
        raise HTTPException(status_code=400, detail=f"Could not find task {task_id}")
    else:
        if (status := _get_task_status()) is not None:
            return status
        raise HTTPException(status_code=400, detail=f"The task never ran.")


def _get_task_status() -> Optional[AsyncResult]:
    if (res := redis_instance.get(REDIS_TASK_ID_KEY)) is not None:
        task_id = res.decode('utf-8')
        return get_celery_task_status(task_id)
    return None
