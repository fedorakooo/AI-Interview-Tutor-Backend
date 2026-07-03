FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gcc \
       libpq-dev \
       build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==2.0.0

WORKDIR /app

COPY libs/shared_models /libs/shared_models
COPY notification-service/poetry.lock notification-service/pyproject.toml ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-interaction --no-ansi

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /libs/shared_models /libs/shared_models

COPY notification-service/config.yaml ./
COPY notification-service/src ./src

CMD ["python3", "-m", "src.main"]
