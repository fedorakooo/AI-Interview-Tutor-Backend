from contextlib import asynccontextmanager

from fastapi import FastAPI
from src.legacy.runtime import legacy_runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with legacy_runtime(app):
        yield
