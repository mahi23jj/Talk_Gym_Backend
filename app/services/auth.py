from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import JWTError, jwt
from sqlmodel import Session, select

from app import db
from app.core.config import settings
from app.schemas.auth import UserSignInschema, UserLoginSchema

from app.models.auth import User

from google.oauth2 import id_token
from google.auth.transport import requests

bycrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth_bearer = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def create_access_token(data: dict, expires_delta: int | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + timedelta(minutes=expires_delta)
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bycrypt_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return bycrypt_context.hash(password)


def get_current_user(token: str = Depends(oauth_bearer)) -> dict:
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        username: str = payload.get("sub")
        email: str = payload.get("email")

        if username is None or email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )
        return {"username": username, "email": email}
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc


async def sign_in_user(user: "UserSignInschema", db: Session) -> str:
    existing_user = (
        db.query(User)
        .filter((User.email == user.email) | (User.username == user.username))
        .first()
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists"
        )

    # Hash the password
    hashed_password = get_password_hash(user.password)

    # Create a new user instance
    new_user = User(
        username=user.username, email=user.email, password_hash=hashed_password
    )

    access_token_expires = settings.access_token_expire_minutes
    access_token = create_access_token(
        data={"sub": new_user.username, "email": new_user.email},
        expires_delta=access_token_expires,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return access_token


async def login_user(users: "UserLoginSchema", db: Session) -> str:
    user = (
        db.query(User)
        .filter((User.email == users.email) | (User.username == users.username))
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    if not verify_password(users.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    access_token_expires = settings.access_token_expire_minutes
    access_token = create_access_token(
        data={"sub": user.username, "email": user.email},
        expires_delta=access_token_expires,
    )
    return access_token


async def login_with_access_token(db: Session, form_data: OAuth2PasswordRequestForm = Depends()) -> str:
    try:
   
        username: str = form_data.username
        password: str = form_data.password

        if username is None or password is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )
        token = await login_user(
                UserLoginSchema(
                    username=form_data.username,
                    password=form_data.password
                ),
                db
            )
        return {"access_token": token, "token_type": "bearer"}
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc



GOOGLE_CLIENT_ID = "your_client_id_here"

def verify_google_token(token: str):
    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )

        return {
            "email": idinfo["email"],
            "name": idinfo.get("name"),
            "sub": idinfo["sub"],  # unique user id
        }

    except Exception as e:
        return None

async def get_user_by_email(db: Session, email: str):
    return db.exec(
        select(User).where(User.email == email)
    ).first()


async def create_google_user(db: Session, token: str,):

    user_data = verify_google_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    
    user = await get_user_by_email(db, user_data["email"])

    if not user:
        user = User(
            email=user_data["email"],
            username=user_data.get("name"),
            google_id=user_data["sub"],  # VERY IMPORTANT
        )

        db.add(user)
        db.commit()
        db.refresh(user)

     

    access_token_expires = settings.access_token_expire_minutes
    access_token = create_access_token(
        data={"sub": user.username, "email": user.email},
        expires_delta=access_token_expires,
    )

    return access_token
