from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.core.config import settings

api_router = APIRouter(prefix=settings.api_v1_prefix)
api_router.include_router(health_router)
