from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlmodel import select

from app.core.config import settings
from app.db.postgran import get_session
from app.models.auth import User
from app.models.interview import Attempt
from app.schemas.workflow import (
    AttemptEnqueueResponse,
    AttemptResultResponse,
    FinalAttemptResultResponse,
    FinalAttemptSubmitResponse,
)
from app.services.auth import get_current_user
from app.services.final_interview import get_attempt_result as get_final_attempt_result
from app.services.final_interview import submit_final_attempt
from app.services.interview import get_attempt_result, submit_normal_attempt
from app.services.rate_limiter import enforce_rate_limit
from app.services.storage_validator import validate_audio_constraints
from app.services.uplode_service import upload_audio_to_cloudinary

router = APIRouter(prefix="/attempt", tags=["Attempt"])


@router.post("/submit/{question_id}", response_model=AttemptEnqueueResponse)
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


@router.post("/submit/final/{attempt_id}", response_model=FinalAttemptSubmitResponse)
async def submit_final_attempt_route(
    attempt_id: int,
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

    attempt = db.get(Attempt, attempt_id)
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if attempt.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Attempt does not belong to user")

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

    return await submit_final_attempt(
        db=db,
        attempt_id=attempt_id,
        audio_url=audio_url,
        duration_seconds=duration_seconds,
        size_bytes=size_bytes,
    )


@router.get("/result/{job_id}", response_model=AttemptResultResponse)
async def get_attempt_by_job_id(
    job_id: int,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_session),
):
    user = db.exec(select(User).where(User.email == current_user["email"])).first()
    if not user:
        user = db.exec(select(User).where(User.username == current_user["username"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return get_attempt_result(db=db, job_id=job_id)


@router.get("/result/final/{job_id}/{attempt_id}", response_model=FinalAttemptResultResponse)
async def get_final_attempt_by_job_id(
    job_id: int,
    attempt_id: int,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_session),
):
    user = db.exec(select(User).where(User.email == current_user["email"])).first()
    if not user:
        user = db.exec(select(User).where(User.username == current_user["username"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    attempt = db.get(Attempt, attempt_id)
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if attempt.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Attempt does not belong to user")

    return get_final_attempt_result(db=db, job_id=job_id, attempt_id=attempt_id)
