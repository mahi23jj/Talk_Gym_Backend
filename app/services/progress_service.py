from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.enums import TrainingMode
from app.models.interview import Attempt


async def upsert_user_progress(
    db: Session,
    user_id: int,
    training_mode: str,
    score: float,
    is_final: bool,
) -> UserProgress:
    progress = db.exec(select(UserProgress).where(UserProgress.user_id == user_id)).first()
    if not progress:
        progress = UserProgress(user_id=user_id)

    progress.total_attempts += 1
    if is_final:
        progress.final_attempts += 1
    progress.best_score = max(progress.best_score, score)
    if progress.average_score == 0:
        progress.average_score = score
    else:
        progress.average_score = round(((progress.average_score * (progress.total_attempts - 1)) + score) / progress.total_attempts, 2)
    progress.updated_at = datetime.now(timezone.utc)

 
    if training_mode == TrainingMode.structure_training.value:
        progress.structure_training_count += 1
    else:
        progress.behavioral_training_count += 1

    progress.last_training_mode = training_mode
    db.add(progress)
    db.commit()
    db.refresh(progress)
    return progress


async def get_user_progress(db: Session, user_id: int) -> UserProgress | None:
    return db.exec(select(UserProgress).where(UserProgress.user_id == user_id)).first()


async def evaluate_progress(first_attempt: Attempt, final_attempt: Attempt) -> dict[str, float | bool]:
    first_score = float((first_attempt.analysis_json or {}).get("overall_score", 0))
    final_score = float((final_attempt.analysis_json or {}).get("overall_score", 0))
    return {
        "score_delta": round(final_score - first_score, 2),
        "previous_score": first_score,
        "current_score": final_score,
        "improved": final_score >= first_score,
    }
