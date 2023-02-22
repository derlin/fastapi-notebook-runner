# Dockerfile
# Uses multi-stage builds requiring Docker 17.05 or higher
# See https://docs.docker.com/develop/develop-images/multistage-build/
# Inspiration: https://github.com/svx/poetry-fastapi-docker

# ===================================================
# 'python-base' contains shared environment variables
# ===================================================
FROM python:3.11-slim-bullseye AS python-base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    WORKDIR="/opt/setup" \
    VENV_PATH="/opt/setup/.venv"

ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

# ====================================================================
# builder-base is used to build dependencies (poetry + only main deps)
# ====================================================================
FROM python-base AS builder-base

# hadolint ignore=DL3008
RUN buildDeps="build-essential" \
    && apt-get update \
    && apt-get install --no-install-recommends -y \
        curl \
        vim \
        netcat \
    && apt-get install -y --no-install-recommends $buildDeps \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry - respects $POETRY_VERSION & $POETRY_HOME
ENV POETRY_VERSION=1.3.2
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=${POETRY_HOME} python3 - --version ${POETRY_VERSION} && \
    chmod a+x /opt/poetry/bin/poetry

# We copy our Python requirements here to cache them
# and install only runtime deps using poetry
WORKDIR $WORKDIR
COPY ./poetry.lock ./pyproject.toml ./
RUN poetry install --only main

# ==============================================
# 'development' is used for linting, tests, etc
# ==============================================
FROM builder-base as development

RUN poetry install --with dev # also install dev dependencies
COPY --chown=poetry:poetry ./cockpit_fastapi ./cockpit_fastapi

# Check formatting
RUN black --check cockpit_fastapi

# Create a dummy file that will be copied into the final image, to ensure this stage is built
# hadolint ignore=DL3059
RUN touch ./test_successful

# =====================================
# 'production' stage is the final image
# =====================================
FROM python-base AS production
ENV FASTAPI_ENV=production
ENV WORKERS=1
ENV LOG_LEVEL=INFO

# Copy only the runtime dependencies from builder-base
COPY --from=builder-base $VENV_PATH $VENV_PATH
# Copy the dummy file from the development stage to ensure the latter is executed,
# since in recent Docker implementations only stages used in the final images are processed.
COPY --from=development $WORKDIR/test_successful /tmp

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Create user with the name poetry
RUN groupadd -g 1500 poetry && \
    useradd -m -u 1500 -g poetry poetry

COPY --chown=poetry:poetry ./cockpit_fastapi /app/cockpit_fastapi
COPY --chown=poetry:poetry ./script.ipynb /app/script.ipynb

USER poetry
WORKDIR /app

# hadolint ignore=DL3025
ENTRYPOINT /docker-entrypoint.sh $0 $@
CMD [ "fastapi" ]
