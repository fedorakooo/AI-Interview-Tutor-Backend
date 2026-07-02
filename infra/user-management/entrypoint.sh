#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting user-management service..."
exec uvicorn src.main:app --host 0.0.0.0 --port 8000
