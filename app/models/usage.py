from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.auth import User


class AIUsage(SQLModel, table=True):
    __tablename__ = "ai_usage"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    usage_date: date = Field(index=True)
    ai_requests_count: int = Field(default=0, ge=0)
    voice_requests_count: int = Field(default=0, ge=0)
    tokens_used: int = Field(default=0, ge=0)

    user: Mapped[Optional["User"]] = Relationship(back_populates="ai_usage")
