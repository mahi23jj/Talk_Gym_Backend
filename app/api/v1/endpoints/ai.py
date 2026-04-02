from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.core.config import settings
from app.db.postgran import get_session
from app.models.auth import User
from app.schemas.usage import AIRequestSchema, AIResponseSchema, UsageSummarySchema
from app.services.auth import get_current_user
from app.services.rate_limiter import enforce_rate_limit
from app.services.usage_tracker import enforce_and_increment_usage

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/process", response_model=AIResponseSchema)
async def process_ai_request(
    payload: AIRequestSchema,
    db=Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    user = db.exec(select(User).where(User.email == current_user["email"])).first()
    if not user:
        user = db.exec(select(User).where(User.username == current_user["username"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await enforce_rate_limit(
        db=db,
        user_id=user.id,
        endpoint="/api/v1/ai/process",
        minute_limit=settings.rate_limit_per_minute,
        hour_limit=settings.rate_limit_per_hour,
    )

    usage = await enforce_and_increment_usage(
        db=db,
        user=user,
        is_voice=payload.is_voice,
        estimated_tokens=payload.estimated_tokens,
    )

    return AIResponseSchema(
        message="AI request accepted and processed",
        usage=UsageSummarySchema.model_validate(usage),
    )
