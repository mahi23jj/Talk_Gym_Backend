from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.db.postgran import get_session
from app.models.auth import User
from app.schemas.workflow import (
    CurrentTrainingResponse,
    TrainingGuidanceResponse,
    TrainingNextRequest,
    TrainingNextResponse,
    TrainingSubmitRequest,
    TrainingSubmitResponse,
)
from app.services.auth import get_current_user
from app.services.training_service import (
    get_current_training,
    get_training_guidance,
    move_to_next_training,
    submit_training_attempt,
)
from app.models.interview import TrainingMode

router = APIRouter(prefix="/training", tags=["Training"])


@router.post("/submit", response_model=TrainingSubmitResponse)
async def submit_training(
    payload: TrainingSubmitRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_session),
):
    user = db.exec(select(User).where(User.email == current_user["email"])).first()
    if not user:
        user = db.exec(select(User).where(User.username == current_user["username"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return await submit_training_attempt(
        db=db,
        user_id=user.id,
        attempt_id=payload.attempt_id,
        training_type=payload.training_type,
        transcript=payload.transcript,
    )


@router.get("/current/{attempt_id}", response_model=CurrentTrainingResponse)
async def current_training(
    attempt_id: int,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_session),
):
    user = db.exec(select(User).where(User.email == current_user["email"])).first()
    if not user:
        user = db.exec(select(User).where(User.username == current_user["username"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return await get_current_training(db=db, attempt_id=attempt_id, user_id=user.id)


@router.post("/next", response_model=TrainingNextResponse)
async def next_training(
    payload: TrainingNextRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_session),
):
    user = db.exec(select(User).where(User.email == current_user["email"])).first()
    if not user:
        user = db.exec(select(User).where(User.username == current_user["username"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return await move_to_next_training(db=db, attempt_id=payload.attempt_id, user_id=user.id)


@router.get("/guidance/{training_mode}", response_model=TrainingGuidanceResponse)
async def training_guidance(training_mode: TrainingMode):
    return get_training_guidance(training_mode)
