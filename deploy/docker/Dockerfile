# Base image
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim AS python-base

# Stage 1: Build stage
FROM python-base AS builder

ARG POETRY_VERSION=1.8.3

ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  POETRY_VERSION=${POETRY_VERSION} \
  POETRY_VIRTUALENVS_IN_PROJECT=true \
  POETRY_NO_INTERACTION=1

RUN apt-get update && \
  apt-get install --no-install-recommends -y \
  build-essential \
  curl \
  git \
  && curl -sSL https://install.python-poetry.org | python - \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app
COPY pyproject.toml poetry.lock* ./

RUN poetry install --no-root --only main

COPY . .
RUN poetry build

# Stage 2: Runtime stage
FROM python-base AS runtime

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && \
  apt-get install --no-install-recommends -y \
  git \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/dist/*.whl /app/

RUN pip install --no-cache-dir /app/*.whl \
  && rm -rf /app/*.whl \
  && pip uninstall --yes pip

ENTRYPOINT ["galaxy", "run"]
