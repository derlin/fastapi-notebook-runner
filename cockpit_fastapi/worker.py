import os

from celery import Celery
from celery.result import AsyncResult
from cockpit_fastapi.executor import execute_notebook

REDIS_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")

celery_app = Celery(__name__)
celery_app.conf.broker_url = REDIS_URL
celery_app.conf.result_backend = REDIS_URL
celery_app.conf.task_track_started = True


print(celery_app.conf)


@celery_app.task(name="run_task")
def run_celery_task():
    return execute_notebook()


def get_celery_task_status(task_id: str) -> AsyncResult:
    return celery_app.AsyncResult(task_id)


def revoke_celery_task(task_id: str) -> None:
    celery_app.control.revoke(task_id, terminate=True, signal='SIGKILL')
