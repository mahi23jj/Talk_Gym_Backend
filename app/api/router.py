from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.ai import router as ai_router
from app.api.v1.endpoints.attempts import router as attempts_router
from app.api.v1.endpoints.questions import router as questions_router
from app.api.v1.endpoints.training import router as training_router
from app.api.v1.endpoints.upload import router as upload_router
from app.core.config import settings

api_router = APIRouter(prefix=settings.api_v1_prefix)
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(ai_router)
api_router.include_router(questions_router)
api_router.include_router(attempts_router)
api_router.include_router(training_router)
api_router.include_router(upload_router)
