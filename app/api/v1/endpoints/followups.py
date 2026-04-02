from fastapi import APIRouter, Depends

from app.db.postgran import get_session
from app.models.interview import TrainingMode
from app.schemas.interview import FollowUpResponseSchema
from app.services.training_service import get_followups_by_mode

router = APIRouter(prefix="/followups", tags=["Followups"])


@router.get("/{training_mode}", response_model=FollowUpResponseSchema)
async def get_followups(training_mode: TrainingMode, db=Depends(get_session)):
    followups = await get_followups_by_mode(db, training_mode.value)
    return FollowUpResponseSchema(training_mode=training_mode, followups=followups)
