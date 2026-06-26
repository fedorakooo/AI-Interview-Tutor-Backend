from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.v1.router import router

app = FastAPI()

app.include_router(router)

app.mount("/static", StaticFiles(directory="src/static"), name="static")


@app.get("/")
async def root():
    return {
        "endpoints": {
            "interview_client": "/static/interview_client.html",
        }
    }
