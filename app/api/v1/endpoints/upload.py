from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from app.services.ai_service import mock_transcript
from app.services.uplode_service import upload_audio_to_cloudinary
from sqlmodel import select

from app.core.config import settings
from app.db.postgran import get_session
from app.models.auth import User
from app.models.recording import Recording
from app.schemas.audio import AudioUploadResponse
from app.services.auth import get_current_user
from app.services.rate_limiter import enforce_rate_limit
from app.services.storage_validator import validate_audio_constraints

router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("/audio", response_model=AudioUploadResponse)
async def upload_audio(
    question_id: int = Form(...),
    duration_seconds: int = Form(...),
    audio: UploadFile = File(...),
    db=Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    user = db.exec(select(User).where(User.email == current_user["email"])).first()
    if not user:
        user = db.exec(
            select(User).where(User.username == current_user["username"])
        ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

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

    simulated_audio_url = f"storage://uploads/{user.id}/{int(datetime.now(timezone.utc).timestamp())}_{audio.filename}"

    audio_url = await upload_audio_to_cloudinary(simulated_audio_url, attempt_type)

    transcript = mock_transcript(audio_url)

    recording = Recording(
        user_id=user.id,
        question_id=question_id,
        audio_url=audio_url,
        duration_seconds=duration_seconds,
        size_bytes=size_bytes,
        transcription=transcript,
    )
    db.add(recording)
    db.commit()
    db.refresh(recording)

    return AudioUploadResponse(
        recording_id=recording.id,
        audio_url=recording.audio_url,
        size_bytes=recording.size_bytes,
        duration_seconds=recording.duration_seconds,
    )
