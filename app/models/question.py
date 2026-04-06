from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel, Relationship


class QuestionTagLink(SQLModel, table=True):
    question_id: int = Field(foreign_key="question.id", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", primary_key=True)


class Tag(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)

    questions: list["Question"] = Relationship(
        back_populates="tags", link_model=QuestionTagLink
    )


class Question(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True, max_length=200)
    description: str
    day_unlock: int = Field(ge=1, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    tags: list["Tag"] = Relationship(
        back_populates="questions", link_model=QuestionTagLink
    )
