import logging
import os
import time
from random import randint

from celery import Celery
from celery.result import AsyncResult

REDIS_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")

celery_app = Celery(__name__)
celery_app.conf.broker_url = REDIS_URL
celery_app.conf.result_backend = REDIS_URL

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@celery_app.task(name="run_task")
def run_celery_task():
    time.sleep(30)
    return f"hello {randint(10, 99)}"


def get_celery_task_status(task_id: str) -> AsyncResult:
    return celery_app.AsyncResult(task_id)


def revoke_celery_task(task_id: str) -> None:
    celery_app.control.revoke(task_id, terminate=True, signal='SIGKILL')
