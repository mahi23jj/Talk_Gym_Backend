from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class UsageSummarySchema(BaseModel):
    usage_date: date
    ai_requests_count: int = Field(ge=0)
    voice_requests_count: int = Field(ge=0)
    tokens_used: int = Field(ge=0)

    model_config = ConfigDict(from_attributes=True)


class AIRequestSchema(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    is_voice: bool = False
    estimated_tokens: int = Field(default=0, ge=0)


class AIResponseSchema(BaseModel):
    message: str
    usage: UsageSummarySchema
