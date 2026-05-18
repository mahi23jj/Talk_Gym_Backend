from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.db.postgran import get_session
from app.models.auth import User
from app.schemas.workflow import (
    BehavioralTrainingSubmitResponse,
    CurrentTrainingResponse,
    TrainingGuidanceResponse,
    TrainingNextRequest,
    TrainingNextResponse,
    TrainingSubmitRequest,
    TrainingSubmitResponse,
)
from app.services.beheviral_training import get_behvioral_attempt_result, summit_behevioral_traning
from app.services.auth import get_current_user_id
from app.services.training_service import (
    get_current_training,
    get_training_guidance,
    move_to_next_training,
    submit_training_attempt,
)
from app.models.enums import TrainingMode

router = APIRouter(prefix="/training", tags=["Training"])


@router.post("/submit", response_model= BehavioralTrainingSubmitResponse)
async def submit_training(
    payload: TrainingSubmitRequest,
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_session),
):

    return await summit_behevioral_traning(
            db=db,
            user_id=user_id,
            job_id=payload.attempt_id,
            transcript=payload.transcript,
        )



@router.get("/results/{job_id}")
async def get_training_results(
    job_id: int,
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_session),
):
    
    return await get_behvioral_attempt_result(
            db=db,
            job_id=job_id
        )
           

@router.get("/current/{attempt_id}", response_model=CurrentTrainingResponse)
async def current_training(
    attempt_id: int,
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_session),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return await get_current_training(db=db, attempt_id=attempt_id, user_id=user.id)


@router.post("/next", response_model=TrainingNextResponse)
async def next_training(
    payload: TrainingNextRequest,
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_session),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return await move_to_next_training(db=db, attempt_id=payload.attempt_id, user_id=user.id)


@router.get("/guidance/{training_mode}", response_model=TrainingGuidanceResponse)
async def training_guidance(training_mode: TrainingMode):
    return get_training_guidance(training_mode)
