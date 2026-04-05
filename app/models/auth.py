
# user table
from app.models.interview import Attempt
from app.models.question import Recording
from sqlmodel import SQLModel, Field , Relationship
from typing import Optional

from app.models.usage import AIUsage

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    password_hash: str

    recordings: list["Recording"] = Relationship(back_populates="user")
    attempts: list["Attempt"] = Relationship(back_populates="user")
    ai_usage: list["AIUsage"] = Relationship(back_populates="user")



