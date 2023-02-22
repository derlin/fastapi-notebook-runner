# Exploration day: Cockpit FastAPI

This repository contains the code of a small REST APi to execute a Jupyter Notebook on-demand.
Hit `/start` and it will start the execution. Hit `/progress` to know the status of the execution. In case of failure,
hit `/output` to see the stacktrace. If you want to stop the execution, hit `/kill`.
If you forgot all about the above, hit `/docs`.

NOTE: only one execution can be requested at a time: hitting `/start` twice in a row, the second request will return an error `400`,
saying an execution was already planned.

## Technologies

* the API is implemented using [FastAPI](https://fastapi.tiangolo.com/), "a modern, fast (high-performance), 
  web framework for building APIs with Python 3.7+ based on standard Python type hints"
* as Python multi-threading is crap, the background tasks are handled by [celery](https://docs.celeryq.dev/en/stable/),
  "*a task queue with focus on real-time processing, while also supporting task scheduling*"
* Celery requires a broker (to transport messages and events) and optionally a backend (to store results). It supports many implementations,
  but [Redis](https://redis.io/) seemed the best option as it is (a) very fast and (b) very easy to setup.
* Celery is very powerful, but doesn't provide a built-in way to limit the number of tasks (to one in our case).
  For that, and since we already have Redis installed anyway, I am using a [Redis Lock](https://redis-py.readthedocs.io/en/v4.1.2/lock.html)
  in the FastAPI application directly (more on this later) 
* FastAPI is an ASGI application. You thus need an ASGI server. The FastAPI docs recommends uvicorn for development,
  and I used [gunicorn](https://gunicorn.org/) with a uvicorn worker class in production (i.e. in the Dockerfile)
* The notebook is executed using the [nbconvert Python API](https://nbconvert.readthedocs.io/en/latest/execute_api.html)

## Local development

This repo uses poetry for dependency management. If you haven't installed it already, see https://python-poetry.org/docs/.
After cloning the repo, simply run `poetry install`. This will create a virtual environment (`.venv`) and install all the
dependencies (production + development).


To develop locally, you need a redis instance running:
```bash
docker run --rm --name some-redis -p 6379:6379 -d redis
```

Then, start both celery and FastAPI in reload mode (this means you can work on the code, and every change will be hot reloaded 😍):
```bash
# start celery
# ! you need watchdog installed: brew install watchdog
watchmedo auto-restart --directory=./cockpit_fastapi --pattern=worker.py  -- celery --app=cockpit_fastapi.worker.celery_app worker --concurrency=1 --loglevel=info
 
# start fastapi
uvicorn cockpit_fastapi.main:app --reload
```

You now have access to the application on **port 8000**. Happy coding!

## Before you push

Ensure you have formatted your source files following PEP8.
Simply run the following in your terminal (Dockerfile build will fail otherwise):
```bash
poetry run black cockpit_fastapi
```
