# syntax=docker/dockerfile:1.6
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl ca-certificates \
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==1.8.3

COPY pyproject.toml ./
RUN poetry config virtualenvs.create false \
  && poetry install --only main --no-interaction --no-ansi --no-root

COPY src ./src

# Juniper runs as a long-lived event consumer + periodic loops. It exposes
# no HTTP/TCP port, so whichever host runs this (Railway, Fly, etc.) needs
# its default port-based healthcheck disabled/unset for this service —
# liveness is "process still running", not a listening socket.
CMD ["python", "-m", "src"]
