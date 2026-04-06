from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.db.postgran import get_session
from app.models.auth import User
from app.schemas.workflow import AttemptSubmitRequest, AttemptSubmitResponse
from app.services.auth import get_current_user
from app.services.interview import submit_normal_attempt

router = APIRouter(prefix="/attempt", tags=["Attempt"])


@router.post("/submit", response_model=AttemptSubmitResponse)
async def submit_attempt(
    payload: AttemptSubmitRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_session),
):
    user = db.exec(select(User).where(User.email == current_user["email"])).first()
    if not user:
        user = db.exec(select(User).where(User.username == current_user["username"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await submit_normal_attempt(
        db=db,
        user_id=user.id,
        question_id=payload.question_id,
        audio_url=payload.audio_url,
        duration_seconds=payload.duration_seconds,
        size_bytes=payload.size_bytes,
        audio_input=payload.audio_input,
    )
    return result
