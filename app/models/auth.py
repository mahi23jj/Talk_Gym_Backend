from typing import TYPE_CHECKING, List, Optional

from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.interview import Attempt
    from app.models.recording import Recording
    from app.models.usage import AIUsage

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    password_hash: Optional[str] = None

    google_id: Optional[str] = Field(default=None, unique=True, index=True)

    recordings: Mapped[List["Recording"]] = Relationship(back_populates="user")
    attempts: Mapped[List["Attempt"]] = Relationship(back_populates="user")
    ai_usage: Mapped[List["AIUsage"]] = Relationship(back_populates="user")



