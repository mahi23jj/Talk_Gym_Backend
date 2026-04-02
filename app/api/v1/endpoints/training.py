from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.db.postgran import get_session
from app.models.interview import Attempt
from app.schemas.interview import TrainingSessionSchema
from app.services.training_service import build_training_session

router = APIRouter(prefix="/training", tags=["Training"])


@router.get("/{attempt_id}", response_model=TrainingSessionSchema)
async def get_training_session(attempt_id: int, db=Depends(get_session)):
    attempt = db.get(Attempt, attempt_id)
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    return await build_training_session(db, attempt)
