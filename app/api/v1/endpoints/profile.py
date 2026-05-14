from fastapi import APIRouter, Depends
from app.db.postgran import get_session
from app.services.auth import get_current_user_id
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("")
async def get_profile(
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_session),
):
    return await ProfileService.get_profile(
        db=db,
        user_id= user_id,
    )