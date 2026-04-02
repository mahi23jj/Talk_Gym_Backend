from fastapi import APIRouter, Depends, HTTPException, status

from app.db.postgran import get_session
from app.schemas.interview import ProgressSchema
from app.services.progress_service import get_user_progress

router = APIRouter(prefix="/progress", tags=["Progress"])


@router.get("/{user_id}", response_model=ProgressSchema)
async def get_progress(user_id: int, db=Depends(get_session)):
    progress = await get_user_progress(db, user_id)
    if not progress:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Progress not found")
    return progress
