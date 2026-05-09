from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import BackgroundTasks, File, HTTPException, UploadFile, status
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

from app.models.job import Job
from app.models.interview import InterviewAnalysis, InterviewSession

from app.core.redis import async_redis_client, TRANSCRIPTION_QUEUE
from app.services.uplode_service import upload_audio_to_cloudinary


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
        job_entry = Job(status="pending")
        session = InterviewSession(
            user_id=user_id,
            question_id=question_id,
        )

        db.add(job_entry)
        db.add(session)
        db.flush()
        
        db_time_ms = (time.perf_counter() - fn_start) * 1000
        print(f"[TIMING:submit_normal_attempt] DB create+flush: {db_time_ms:.2f}ms, job_id={job_entry.id}, session_id={session.id}")

        payload = {
            "job_id": job_entry.id,
            "user_id": user_id,
            "question_id": question_id,
            "session_id": session.id,
            "duration_seconds": duration_seconds,
            "size_bytes": size_bytes,
            "audio_url": audio_url,
        }

        redis_start = time.perf_counter()
        await async_redis_client.rpush(
            TRANSCRIPTION_QUEUE,
            json.dumps(payload),
        )
        redis_time_ms = (time.perf_counter() - redis_start) * 1000
        print(f"[TIMING:submit_normal_attempt] Redis enqueue: {redis_time_ms:.2f}ms")
        
        db.commit()
        commit_time_ms = (time.perf_counter() - fn_start) * 1000
        print(f"[TIMING:submit_normal_attempt] Commit: {commit_time_ms:.2f}ms")
        
        total_fn_ms = (time.perf_counter() - fn_start) * 1000
        print(f"[TIMING:submit_normal_attempt] TOTAL: {total_fn_ms:.2f}ms")

        return {
            "job_id": job_entry.id,
            "message": "Attempt submitted successfully and is being processed.",
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred while submitting the attempt: {exc}",
            )


async def process_audio_summition(content: bytes , payload: dict[str, Any],queue: str , audio: str ) -> dict[str, Any]:

    try:
        audio_url = upload_audio_to_cloudinary(content, audio)

        payload["audio_url"] = audio_url

    

    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Audio upload failed",
        ) from exc



def get_attempt_result(db: Session, job_id: int) -> dict[str, Any]:
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
    elif job_entry.status == "failed":
        return {
            "status": "failed",
            "message": "Processing of your attempt failed. Please try again.",
        }
    else:

        analysis = db.exec(
            select(InterviewAnalysis).where(
                InterviewAnalysis.attempt_id == job_entry.attempt_id
            )
        ).first()

    if not analysis:
        return {"status": "processing", "message": "Finalizing analysis..."}

    return {
        "status": "done",
        "analysis": analysis,
    }


def get_analysis_result(db: Session, job_id: int) -> dict[str, Any]:

    job_entry = db.get(Job, job_id)
    if not job_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

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


# async def translate_voice_attempt(attempt_id: int, db: Session) -> dict[str, Any]:

#     while True:

#         job_data = async_redis_client.blpop(queue_name, timeout=30)
#         if not job_data:
#             raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Processing timed out. Please try again later.")

#         job_str = job_data[1].decode("utf-8")
#         user_id_str, question_id_str, audio_url, duration_seconds_str, size_bytes_str = job_str.split(":")

#

#         #  do a work to translate voice to text and analyze it, then save to db
#         # For demonstration, we will just mock the transcript and analysis
#         transcript = transcribe_audio(audio_url)
#         analysis_payload = mock_ai_analysis(
#         transcript=transcript,
#         question=f"{question.title}. {question.description}",
#         )


#         transcript = mock_transcript(audio_url)

#         recording = Recording(
#             user_id=user_id,
#             question_id=question.id,
#             audio_url=audio_url,
#             duration_seconds=duration_seconds,
#             size_bytes=size_bytes,
#             transcription=transcript,
#         )
#         db.add(recording)
#         db.commit()
#         db.refresh(recording)

#         analysis_payload = mock_ai_analysis(
#             transcript=transcript,
#             question=f"{question.title}. {question.description}",
#         )

#         ordered_candidates = select_training_mode(analysis_payload)
#         ordered_plan: list[TrainingMode] = []
#         for mode in ordered_candidates:
#             normalized = mode if isinstance(mode, TrainingMode) else TrainingMode(str(mode))
#             if normalized not in ordered_plan:
#                 ordered_plan.append(normalized)

#         attempt = Attempt(
#             user_id=user_id,
#             question_id=question.id,
#             recording_id=recording.id,
#             transcript=transcript,
#         )
#         db.add(attempt)
#         db.commit()
#         db.refresh(attempt)

#         score = int(round(float(analysis_payload.get("overall_score", 0.0)) * 10))
#         feedback = "Mock AI analysis completed for the submitted answer."

#         analysis = InterviewAnalysis(
#             attempt_id=attempt.id,
#             score=score,
#             feedback=feedback,
#             raw_analysis_json=analysis_payload,
#         )
#         db.add(analysis)
#         db.commit()
#         db.refresh(analysis)

#         recommendations: list[TrainingRecommendation] = []
#         for priority, training_type in enumerate(ordered_plan, start=1):
#             row = TrainingRecommendation(
#                 attempt_id=attempt.id,
#                 training_type=training_type,
#                 priority=priority,
#             )
#             db.add(row)
#             recommendations.append(row)

#         progress = TrainingProgress(
#             attempt_id=attempt.id,
#             current_priority=1,
#             completed=False,
#         )
#         db.add(progress)
#         db.commit()

#         for row in recommendations:
#             db.refresh(row)
#         db.refresh(progress)

#         return {
#             "recording": recording,
#             "attempt": attempt,
#             "analysis": analysis,
#             "recommendations": recommendations,
#             "progress": progress,
#         }


#     # attempt = db.get(Attempt, attempt_id)
#     # if not attempt:
#     #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")

#     # transcript = mock_transcript(attempt.recording.audio_url)
#     # attempt.transcript = transcript
#     # db.add(attempt)
#     # db.commit()
#     # db.refresh(attempt)
