from fastapi import FastAPI

from src.api.exception_handler import exception_container
from src.api.v1.router import router
from src.lifespan import lifespan

app = FastAPI(lifespan=lifespan)

app.include_router(router)

exception_container(app)
