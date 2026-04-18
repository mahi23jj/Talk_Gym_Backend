
from typing import Any

from sqlmodel import Session, select

from app.models.interview import Attempt
from fastapi import HTTPException, status

from app.models.job import Job
from app.models.question import Question
from app.models.training import TrainingAnalysis, TrainingAttempt
from app.models.enums import TrainingMode

from app.core.redis import redis_client, ANALYSIS_QUEUE

import json


async def summit_behevioral_traning(
    db: Session,
    user_id: int,
    attempt_id: int,
    transcript: str,

) -> dict[str, Any]:
    attempt = db.get(Attempt, attempt_id)
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if attempt.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Attempt does not belong to user")
     
    previous_attempts = db.exec(
        select(TrainingAttempt).where(
            TrainingAttempt.attempt_id == attempt_id,
            TrainingAttempt.training_type == TrainingMode.behavioral_training,
        )
    ).all()

    for existing in previous_attempts:
        existing_analysis = db.exec(
            select(TrainingAnalysis).where(TrainingAnalysis.training_attempt_id == existing.id)
        ).first()
        if existing_analysis and existing_analysis.passed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Behavioral training already passed for this attempt",
            )

    if len(previous_attempts) >= 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Max behavioral training attempts reached",
        )

    training_attempt = TrainingAttempt(
        attempt_id=attempt_id,
        training_type=TrainingMode.behavioral_training,
        transcript=transcript,
    )
    db.add(training_attempt)
    db.commit()
    db.refresh(training_attempt)
    
    question = db.get(Question, attempt.question_id)
    question_text = f"{question.title}. {question.description}" if question else "Behavioral training follow-up response"

    job_entry = Job(status="pending")

    db.add(job_entry)
    db.commit()
    db.refresh(job_entry)

    payload = {
        "job_id": job_entry.id,
        "user_id": user_id,
        "attempt_id": attempt_id,
        "training_attempt_id": training_attempt.id,
        "question_id": question.id if question else attempt.question_id,
        "question_text": question_text,
        "transcript": transcript,
    }

    redis_client.rpush(
        ANALYSIS_QUEUE,
        json.dumps(payload),
    )


    return {
        "job_id": job_entry.id,
        "training_attempt_id": training_attempt.id,
        "message": "Behavioral training attempt submitted successfully and is being processed.",
    }