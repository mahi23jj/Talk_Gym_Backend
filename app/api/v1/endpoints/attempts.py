from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlmodel import select

from app.core.config import settings
from app.db.postgran import get_session
from app.models.auth import User
from app.schemas.workflow import AttemptSubmitResponse
from app.services.auth import get_current_user
from app.services.interview import submit_normal_attempt
from app.services.rate_limiter import enforce_rate_limit
from app.services.storage_validator import validate_audio_constraints
from app.services.uplode_service import upload_audio_to_cloudinary

router = APIRouter(prefix="/attempt", tags=["Attempt"])


@router.post("/submit/{question_id}", response_model=AttemptSubmitResponse)
async def submit_attempt(
    question_id: int,
    duration_seconds: int = Form(..., alias="duration_sec"),
    audio: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_session),
):
    user = db.exec(select(User).where(User.email == current_user["email"])).first()
    if not user:
        user = db.exec(select(User).where(User.username == current_user["username"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    await enforce_rate_limit(
        db=db,
        user_id=user.id,
        endpoint="/api/v1/upload/audio",
        minute_limit=settings.rate_limit_per_minute,
        hour_limit=settings.rate_limit_per_hour,
    )

    content = await audio.read()
    size_bytes = len(content)

    await validate_audio_constraints(
        db=db,
        user_id=user.id,
        size_bytes=size_bytes,
        duration_seconds=duration_seconds,
        max_size_bytes=settings.max_audio_size_bytes,
        max_duration_seconds=settings.max_audio_duration_seconds,
        daily_upload_limit=settings.daily_audio_upload_limit,
    )

    try:
        audio_url = upload_audio_to_cloudinary(content, audio.filename or "audio.m4a")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Audio upload failed",
        ) from exc

    result = await submit_normal_attempt(
        db=db,
        user_id=user.id,
        question_id=question_id,
        audio_url=audio_url,
        duration_seconds=duration_seconds,
        size_bytes=size_bytes,
    )
    return result
