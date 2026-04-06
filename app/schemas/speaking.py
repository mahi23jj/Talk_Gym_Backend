from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator




class QuestionCreateSchema(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10)
    # they relate many to many, so we just send a list of tag names here. The service layer will handle linking them.
    tags: list[str] = Field(default_factory=list) 
    day_unlock: int = Field(ge=1)


class QuestionReadSchema(QuestionCreateSchema):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TagCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class TagReadSchema(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class TagStatSchema(BaseModel):
    tag: TagReadSchema
    question_count: int = Field(ge=0)


class QuestionTagsUpdateSchema(BaseModel):
    tags: list[str] = Field(default_factory=list)


class QuestionByTagsQuerySchema(BaseModel):
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def parse_tags(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        value = data.get("tags")
        if isinstance(value, str):
            data["tags"] = [item.strip() for item in value.split(",") if item.strip()]
        return data


class QuestionSearchQuerySchema(BaseModel):
    keyword: str = Field(min_length=1)


class QuestionWithCountSchema(BaseModel):
    question: QuestionReadSchema
    count: int = Field(ge=0)


class RecordingCreateSchema(BaseModel):
    user_id: int = Field(gt=0)
    question_id: int = Field(gt=0)
    audio_url: str = Field(min_length=5, max_length=500)
    duration_seconds: int = Field(gt=0)
    size_bytes: int = Field(gt=0)


class RecordingReadSchema(RecordingCreateSchema):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSessionCreateSchema(BaseModel):
    user_id: int = Field(gt=0)
    recording_id: int = Field(gt=0)


class ChatSessionEndSchema(BaseModel):
    is_active: bool = False
    ended_at: datetime


class ChatSessionReadSchema(BaseModel):
    id: int
    user_id: int
    recording_id: int
    is_active: bool
    created_at: datetime
    ended_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)





class AIAnalysisCreateSchema(BaseModel):
    chat_session_id: int = Field(gt=0)
    recording_id: int = Field(gt=0)
    summary: str = Field(min_length=10)
    feedback: str = Field(min_length=10)
    tips: str = Field(min_length=5)
    score: int = Field(ge=0, le=100)


class AIAnalysisReadSchema(AIAnalysisCreateSchema):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
