from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.auth import User
from app.models.usage import AIUsage

FREE_AI_DAILY_LIMIT = 20
FREE_VOICE_DAILY_LIMIT = 10
# PREMIUM_AI_DAILY_LIMIT = 200
# PREMIUM_VOICE_DAILY_LIMIT = 100


async def get_or_create_daily_usage(db: Session, user_id: int) -> AIUsage:
    today = date.today()
    usage = db.exec(
        select(AIUsage).where(AIUsage.user_id == user_id, AIUsage.usage_date == today)
    ).first()

    if usage:
        return usage

    usage = AIUsage(user_id=user_id, usage_date=today)
    db.add(usage)
    db.commit()
    db.refresh(usage)
    return usage


async def enforce_and_increment_usage(
    db: Session,
    user: User,
    is_voice: bool,
    estimated_tokens: int = 0,
) -> AIUsage:
    usage = await get_or_create_daily_usage(db, user.id)

    # is_premium = (user.plan_type or "free").lower() == "premium"
    ai_limit =  FREE_AI_DAILY_LIMIT
    voice_limit =  FREE_VOICE_DAILY_LIMIT

    if usage.ai_requests_count >= ai_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily AI request quota exceeded",
        )

    if is_voice and usage.voice_requests_count >= voice_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily voice analysis quota exceeded",
        )

    usage.ai_requests_count += 1
    if is_voice:
        usage.voice_requests_count += 1
    usage.tokens_used += max(0, estimated_tokens)

    db.add(usage)
    db.commit()
    db.refresh(usage)
    return usage
