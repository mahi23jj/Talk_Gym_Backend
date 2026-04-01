from fastapi import APIRouter, Depends


from app.db.postgran import SessionType


from app.schemas.auth import UserLoginSchema, UserSignInResponseSchema, UserSignInschema
from app.services.auth import login_user, sign_in_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/signin", response_model=UserSignInResponseSchema)
async def signin(signin_data: UserSignInschema, db: SessionType):
    token = await sign_in_user(signin_data, db)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login", response_model=UserSignInResponseSchema)
async def login(login_data: UserLoginSchema, db: SessionType):
    token = await login_user(login_data, db)
    return {"access_token": token, "token_type": "bearer"}
