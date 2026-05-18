from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import BackgroundTasks, File, HTTPException, UploadFile, status
import redis
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

from app.models.job import Job
from app.models.interview import InterviewAnalysis, InterviewSession

from app.core.redis import async_redis_client, TRANSCRIPTION



async def submit_normal_attempt(
    db: Session,
    user_id: int,
    question_id: int,
    duration_seconds: int,
    size_bytes: int,
    audio_url: str,
) -> dict[str, Any]:
    fn_start = time.perf_counter()
    try:
        # Create records - consider if you really need both flush and commit
        job_entry = Job(status="pending")
        session = InterviewSession(
            user_id=user_id,
            question_id=question_id,
        )

        db.add(job_entry)
        db.add(session)

        # Flush to get IDs (synchronous SQLModel Session)
        db.flush()
        db_time_ms = (time.perf_counter() - fn_start) * 1000
        print(f"[TIMING:submit_normal_attempt] DB create+flush: {db_time_ms:.2f}ms")

        payload = {
            "job_id": job_entry.id,
            "user_id": user_id,
            "question_id": question_id,
            "session_id": session.id,
            "duration_seconds": duration_seconds,
            "size_bytes": size_bytes,
            "audio_url": audio_url,
        }

        # Pipeline Redis operations
        redis_start = time.perf_counter()
        pipeline = async_redis_client.pipeline()
        pipeline.rpush(TRANSCRIPTION, json.dumps(payload))
        await pipeline.execute()
        redis_time_ms = (time.perf_counter() - redis_start) * 1000
        print(f"[TIMING:submit_normal_attempt] Redis enqueue: {redis_time_ms:.2f}ms")
        
        db.commit()
        commit_time_ms = (time.perf_counter() - fn_start) * 1000
        print(f"[TIMING:submit_normal_attempt] Commit: {commit_time_ms:.2f}ms")
        
        return {
            "job_id": job_entry.id,
            "message": "Attempt submitted successfully and is being processed.",
        }
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while submitting the attempt: {exc}",
        )



async def get_attempt_result(db: Session, job_id: int) -> dict[str, Any]:
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
    if not job_entry.attempt_id:
        return {
            "status": "processing",
            "message": "Finalizing analysis..."
        }
    
    # Fetch the actual analysis from database
    analysis = db.exec(
        select(InterviewAnalysis).where(
            InterviewAnalysis.attempt_id == job_entry.attempt_id
        )
    ).first()

    if not analysis:
        return {"status": "processing", "message": "Finalizing analysis..."}

    return {
        "status": "done",
        "message": None,
        "analysis": analysis
    }

    


async def get_analysis_result(db: Session, job_id: int) -> dict[str, Any]:

    job_entry = db.get(Job, job_id)
    if not job_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    # Try to get from cache first
    cached = await async_redis_client.get(f"attempt_result:{job_id}")
    if cached:
        return json.loads(cached)

    # Fall back to database
    analysis = db.exec(
        select(InterviewAnalysis).where(
            InterviewAnalysis.attempt_id == job_entry.attempt_id
        )
    ).first()

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    return analysis


