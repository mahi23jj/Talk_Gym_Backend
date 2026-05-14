
from typing import Any

from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from app.core import redis
from app.models.interview import Attempt
from fastapi import HTTPException, status

from app.models.job import Job
from app.models.question import Question
from app.models.training import TrainingAnalysis, TrainingAttempt
from app.models.enums import TrainingMode

from app.core.redis import async_redis_client, ANALYSIS_QUEUE

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
        select(TrainingAttempt)
        .where(
            TrainingAttempt.attempt_id == attempt_id,
            TrainingAttempt.training_type == TrainingMode.behavioral_training,
        )
        .options(selectinload(TrainingAttempt.analysis))
    ).all()

    if len(previous_attempts) >= 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Max behavioral training attempts reached",
        )

    for existing in previous_attempts:
        existing_analysis = existing.analysis
        if existing_analysis and existing_analysis.passed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Behavioral training already passed for this attempt",
            )



    training_attempt = TrainingAttempt(
        attempt_id=attempt_id,
        training_type=TrainingMode.behavioral_training,
        transcript=transcript,
    )
    db.add(training_attempt)
    db.flush()
   
    
    question = db.get(Question, attempt.question_id)
    question_text = f"{question.title}. {question.description}" if question else "Behavioral training follow-up response"

    job_entry = Job(status="pending")

    db.add(job_entry)
    db.commit()
    

    payload = {
        "job_id": job_entry.id,
        "user_id": user_id,
        "attempt_id": attempt_id,
        "training_attempt_id": training_attempt.id,
        "question_id": question.id if question else attempt.question_id,
        "question_text": question_text,
        "transcript": transcript,
    }

    async_redis_client.rpush(
        ANALYSIS_QUEUE,
        json.dumps(payload),
    )


    return {
        "job_id": job_entry.id,
        "training_attempt_id": training_attempt.id,
        "message": "Behavioral training attempt submitted successfully and is being processed.",
    }



async def get_behvioral_attempt_result(db: Session,  training_attempt_id: int , job_id: int) -> dict[str, Any]:
    job_entry = db.get(Job, job_id)
    if not job_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    if job_entry.status == "pending":
        return {
            "status": "pending",
            "message": "Your attempt is still being processed. Please check back later.",
        }
    if job_entry.status == "failed":
        return {
            "status": "failed",
            "message": "Processing of your attempt failed. Please try again.",
        }

        
    cached = await async_redis_client.get(f"behavioral_result:{job_id}")

    if not cached:
        return {"status": "processing", "message": "Finalizing analysis..."}

    return {
        "status": "done",
        "analysis": {
            "id": cached.id,
            "training_attempt_id": cached.training_attempt_id,
            "passed": cached.passed,
            "feedback": cached.feedback,
            "score": cached.score,
        },
    }