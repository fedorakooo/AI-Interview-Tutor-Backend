from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from src.config import settings
from src.infrastructure.user_management.assessment_context_client import UserManagementAssessmentContextClient
from src.legacy.runtime import legacy_runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    user_management = settings.user_management_settings
    async with httpx.AsyncClient(timeout=user_management.timeout_seconds) as http_client:
        app.state.assessment_context_client = UserManagementAssessmentContextClient(
            client=http_client,
            base_url=user_management.url,
            service_token=user_management.internal_service_token,
        )
        async with legacy_runtime(app):
            yield
