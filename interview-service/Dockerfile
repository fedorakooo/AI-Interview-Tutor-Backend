FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==2.1.3

COPY libs/jwt_handler /libs/jwt_handler
COPY libs/shared_models /libs/shared_models
COPY interview-service/poetry.lock interview-service/pyproject.toml ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-interaction --no-ansi

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /libs/jwt_handler /libs/jwt_handler
COPY --from=builder /libs/shared_models /libs/shared_models

COPY interview-service/config.yaml ./
COPY interview-service/src ./src

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=20s \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001", "--timeout-graceful-shutdown", "30"]
