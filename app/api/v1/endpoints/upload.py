from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlmodel import select

from app.core.config import settings
from app.db.postgran import get_session
from app.models.auth import User
from app.models.recording import Recording
from app.schemas.audio import AudioUploadResponse
from app.services.Ai_Transaltion import transcribe_audio
from app.services.auth import get_current_user
from app.services.ai_service import mock_transcript
from app.services.rate_limiter import enforce_rate_limit
from app.services.storage_validator import validate_audio_constraints
from app.services.uplode_service import upload_audio_to_cloudinary

router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("/audio")
async def upload_audio(
    audio: UploadFile = File(...),
):
    text = await transcribe_audio(audio)
    return {"transcript": text}
