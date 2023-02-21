#!/bin/bash

set -e

# activate our virtual environment here
#. /opt/pysetup/.venv/bin/activate

WORKERS=${WORKERS:-1}
LOG_LEVEL=${LOG_LEVEL:-INFO}

usage() {
  echo "Usage: $0 [celery|fastapi]"
  echo "  - fastapi: start the fastapi server"
  echo "  - celery: start the celery worker"
}

if [[ "$1" == "celery" ]]; then
  celery --app=cockpit_fastapi.worker.celery_app worker --concurrency=$WORKERS --loglevel=$LOG_LEVEL
elif [[ "$1" == "fastapi" ]]; then
  gunicorn --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080 -w $WORKERS cockpit_fastapi.main:app --log-level $LOG_LEVEL
else
  echo "Unknown or missing sub-command: '$1'"
  usage
  exit 1
fi
