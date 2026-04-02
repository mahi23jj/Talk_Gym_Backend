from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.db.postgran import get_session
from app.models.auth import User
from app.models.interview import Attempt, InterviewAnalysis
from app.models.speaking import Question
from app.schemas.interview import (
    AttemptReadSchema,
    AttemptResultSchema,
    AttemptSubmitResponseSchema,
    AttemptSubmitSchema,
    FinalAttemptResponseSchema,
    FinalAttemptSchema,
    AnalysisReadSchema,
)
from app.services.ai_service import build_training_instructions
from app.services.auth import get_current_user
from app.services.progress_service import get_user_progress, evaluate_progress
from app.services.training_service import (
    build_training_session,
    create_final_attempt,
    submit_attempt,
)

router = APIRouter(prefix="/attempts", tags=["Attempts"])


@router.post("/", response_model=AttemptSubmitResponseSchema)
async def create_attempt(
    payload: AttemptSubmitSchema,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_session),
):
    user = db.exec(select(User).where(User.email == current_user["email"])).first()
    if not user:
        user = db.exec(select(User).where(User.username == current_user["username"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await submit_attempt(
        db=db,
        user=user,
        question_id=payload.question_id,
        recording_id=payload.recording_id,
        audio_input=payload.audio_input,
    )
    return result


@router.get("/{attempt_id}", response_model=AttemptResultSchema)
async def get_attempt_result(attempt_id: int, db=Depends(get_session)):
    analysis = db.exec(select(InterviewAnalysis).where(InterviewAnalysis.attempt_id == attempt_id)).first()
    attempt = db.get(Attempt, attempt_id)
    if not analysis or not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return {"attempt": attempt, "analysis": analysis}


@router.get("/detail/{attempt_id}", response_model=AttemptReadSchema)
async def get_attempt_detail(attempt_id: int, db=Depends(get_session)):
    attempt = db.get(Attempt, attempt_id)
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    return attempt


@router.post("/{attempt_id}/final", response_model=FinalAttemptResponseSchema)
async def submit_final_attempt(
    attempt_id: int,
    payload: FinalAttemptSchema,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_session),
):
    user = db.exec(select(User).where(User.email == current_user["email"])).first()
    if not user:
        user = db.exec(select(User).where(User.username == current_user["username"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await create_final_attempt(
        db=db,
        user=user,
        attempt_id=attempt_id,
        recording_id=payload.recording_id,
        audio_input=payload.audio_input,
    )
    return result
