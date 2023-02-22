import datetime
import logging
from typing import Optional

import celery.states
from celery.result import AsyncResult
from cockpit_fastapi.worker import (
    run_celery_task,
    get_celery_task_status,
    revoke_celery_task,
    REDIS_URL,
)
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter
from pydantic import BaseModel
from redis import Redis
from redis.lock import Lock as RedisLock
from starlette_exporter import PrometheusMiddleware, handle_metrics

REDIS_TASK_ID_KEY = (
    "current_task_id"  # Will store the last/current celery task ID in Redis
)

app = FastAPI()

redis_instance = Redis.from_url(url=REDIS_URL)
celery_lock = RedisLock(redis_instance, name="task_lock")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", handle_metrics)

execution_counter = Counter(
    name="notebook_executions_total", documentation="Number of notebook executions"
)


class TaskResponse(BaseModel):
    id: str
    status: str
    date: Optional[datetime.datetime] = None


@app.get("/ping")
def api_ping() -> str:
    return "I am alive"


@app.get(
    "/start",
    name="Start task",
    description="Trigger the execution of the notebook. Will fail if an execution is already in progress.",
)
def api_start() -> TaskResponse:
    if not celery_lock.acquire(blocking_timeout=3):  # timeout in seconds
        raise HTTPException(status_code=401, detail="Could not acquire lock")
    try:
        if (
            current_task := _get_task_status()
        ) is not None and not current_task.ready():
            raise HTTPException(
                status_code=401,
                detail=f"Another task is already running: {current_task.task_id}",
            )
        task = run_celery_task.delay()
        redis_instance.set(REDIS_TASK_ID_KEY, task.task_id)
        execution_counter.inc()  # Update prometheus metric
        return TaskResponse(id=task.task_id, status=celery.states.PENDING)
    finally:
        celery_lock.release()


@app.get(
    "/progress",
    name="Query status",
    description="Get the status of the current task. Use the task_id parameter to query a specific task.",
)
def api_progress(task_id: Optional[str] = None) -> TaskResponse:
    task_status = _task_status_or_http_error(task_id)
    return _task_status_to_response(task_status)


@app.get(
    "/output",
    name="Get output",
    description="Get the status of the current task. Use the task_id parameter to query a specific task.",
    response_class=PlainTextResponse,
    response_description="The stacktrace in case of an error.",
)
def api_error(task_id: Optional[str] = None):
    task_status = _task_status_or_http_error(task_id)
    match task_status.status:
        case celery.states.FAILURE:
            return f"❗❗Task {task_status.task_id} finished with failure ❗❗\n\n{task_status.traceback}\n"
        case celery.states.SUCCESS:
            return f"✅ Task {task_status.task_id} finished with success.\n"

    return PlainTextResponse(
        status_code=400,
        content=f"Only tasks success/failure has output. Task {task_status.task_id} is in state {task_status.status}.",
    )


@app.get("/kill", name="Abort task", description="Kill the current task.")
def api_kill():
    task_status = _task_status_or_http_error(None)
    revoke_celery_task(task_status.task_id)
    return _task_status_to_response(task_status)


def _task_status_to_response(task_result: AsyncResult) -> TaskResponse:
    return TaskResponse(
        id=task_result.task_id, status=task_result.status, date=task_result.date_done
    )


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
        task_id = res.decode("utf-8")
        return get_celery_task_status(task_id)
    return None
