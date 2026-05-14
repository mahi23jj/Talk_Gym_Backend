from typing import Optional, List
from pydantic import BaseModel


class TrialStatus(BaseModel):
    interviews_used: int
    interviews_limit: int
    remaining: int


class ProgressSummary(BaseModel):
    total_questions_attempted: int
    completed_sessions: int
    avg_improvement: float


class CategoryProgress(BaseModel):
    category: str
    attempts: int
    avg_score: float


class QuestionHistoryItem(BaseModel):
    session_id: int
    question_id: int
    initial_score: Optional[int]
    final_score: Optional[int]
    improvement: Optional[int]
    recommendation_type: Optional[str]
    completed: bool


class ContinueSession(BaseModel):
    session_id: int
    question_id: int
    next_stage: str


class ProfileResponse(BaseModel):
    username: str
    email: str
    trial_status: TrialStatus
    progress: ProgressSummary
    categories: List[CategoryProgress]
    history: List[QuestionHistoryItem]
    continue_session: Optional[ContinueSession]