# Notebook Runner using FastAPI and Celery

This repository contains the code of a small REST API to execute a Jupyter Notebook on-demand.
Hit `/start` and it will start the execution. Hit `/progress` to know the status of the execution. In case of failure,
hit `/output` to see the stack trace. If you want to stop the execution, hit `/kill`.
If you forgot all about the above, hit `/docs`.

NOTE: only one execution can be requested at a time: hitting `/start` twice in a row, the second request will return an error `400`,
saying an execution was already planned.

## Technologies

* the API is implemented using [FastAPI](https://fastapi.tiangolo.com/), "a modern, fast (high-performance), 
  web framework for building APIs with Python 3.7+ based on standard Python type hints"
* as Python multi-threading is crap, the background tasks are handled by [celery](https://docs.celeryq.dev/en/stable/),
  "*a task queue with focus on real-time processing, while also supporting task scheduling*"
* Celery requires a broker (to transport messages and events) and optionally a backend (to store results). It supports many implementations,
  but [Redis](https://redis.io/) seemed the best option as it is (a) very fast and (b) very easy to set up.
* Celery is very powerful but doesn't provide a built-in way to limit the number of tasks (to one in our case).
  For that, and since we already have Redis installed anyway, I am using a [Redis Lock](https://redis-py.readthedocs.io/en/v4.1.2/lock.html)
  in the FastAPI application directly (more on this later) 
* FastAPI is an ASGI application. You thus need an ASGI server. The FastAPI doc recommends uvicorn for development,
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
# ! you need watchdog installed: pip install watchdog
watchmedo auto-restart --directory=./nb_runner --pattern=worker.py\
  -- celery --app=nb_runner.worker.celery_app worker --concurrency=1 --loglevel=info
 
# start fastapi
uvicorn nb_runner.main:app --reload
```

You now have access to the application on **port 8000**. Happy coding!

## Before you push

Ensure you have formatted your source files following PEP8.
Simply run the following in your terminal (Dockerfile build will fail otherwise):
```bash
poetry run black nb_runner
```

## Running on a local k3d cluster

First, start a k3d cluster with a local registry:
```bash
k3d registry create registry.localhost --port 5555
k3d cluster create test --registry-use k3d-registry.localhost:5555 --api-port 6550 -p "80:80@loadbalancer"
```

To be able to push to the registry, you need to add the following to your `/etc/hosts`:
```bash
echo "127.0.0.1 k3d-registry.localhost" | sudo tee -a /etc/hosts
```

Now, build the image and push it to the local registry:
```bash
# Using regular docker
docker build k3d-registry.localhost:5555/nb-runner .
docker push k3d-registry.localhost:5555/nb-runner

# Using buildx (you need amd64 image for k3d)
docker buildx build --platform=linux/amd64 --pull --push -t k3d-registry.localhost:5555/nb-runner .
```

Final step, you need to configure a bit the Helm Chart for k3d. For that, create a `values-k3d.yaml` file and add:
```yaml
ingress:
  enabled: true
  host: nb-runner  # <- this needs to match an entry in /etc/hosts redirecting to 127.0.0.1
  path: /

nb_runner:
  image:
    name: k3d-registry.localhost:5555/nb-runner
```

With this, you are ready to deploy to k3d:
```bash
helm install nb-runner helm/nb-runner --values values-k3d.yaml
```

If you want to test the ingress, you need to add the following to your `etc/hosts` as well (you can change the host, just don't
forget to change it in the `values-k3d.yaml` AND the `/etc/hosts`):
```bash
echo "127.0.0.1 nb-runner" | sudo tee -a /etc/hosts
```

With this entry, you can now go to http://nb-runner/docs. Congrats, you deployed to Kubernetes!
