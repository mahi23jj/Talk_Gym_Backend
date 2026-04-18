from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.enums import AttemptStage
from app.models.job import Job
from app.models.interview import Attempt, InterviewAnalysis
from app.models.question import Question

from app.core.redis import redis_client, TRANSCRIPTION_QUEUE 


async def submit_final_attempt(
    db: Session,
    attempt_id: int,
    audio_url: str,
    duration_seconds: int,
    size_bytes: int,
) -> dict[str, Any]:

    attempt = db.get(Attempt, attempt_id)
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found"
        )

    question = db.exec(select(Question).where(Question.id == attempt.question_id)).one_or_none()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Question not found"
        )

    job_entry = Job(status="pending")

    db.add(job_entry)
    db.commit()
    db.refresh(job_entry)

    payload = {
        "job_id": job_entry.id,
        "user_id": attempt.user_id,
        "question_id": question.id,
        "question_title": question.title,
        "question_description": question.description,
        "audio_url": audio_url,
        "duration_seconds": duration_seconds,
        "size_bytes": size_bytes,
        "stage": AttemptStage.FINAL.value,
    }

    redis_client.rpush(
        TRANSCRIPTION_QUEUE,
        json.dumps(payload),
    )
    return {
        "job_id": job_entry.id,
        "attempt_id": attempt_id,
        "message": "Attempt submitted successfully and is being processed.",
    }


def get_attempt_result(db: Session, job_id: int, attempt_id: int) -> dict[str, Any]:
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
        initial_attempt = db.get(Attempt, attempt_id)
        final_attempt = db.get(Attempt, job_entry.attempt_id)

        initial_attempt_analysis = db.exec(
            select(InterviewAnalysis).where(
                InterviewAnalysis.attempt_id == attempt_id
            )
        ).one_or_none()

        attempt_analysis = db.exec(
            select(InterviewAnalysis).where(
                InterviewAnalysis.attempt_id == job_entry.attempt_id
            )
        ).one_or_none()

        score_diff = None
        feedback_diff = None
        if initial_attempt_analysis and attempt_analysis:
            score_diff = attempt_analysis.score - initial_attempt_analysis.score
            feedback_diff = (
                f"Initial feedback: {initial_attempt_analysis.feedback}\n"
                f"Final feedback: {attempt_analysis.feedback}"
            )



        if not attempt_analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found"
            )
        
        return {
            "status": "done",
            "attempt": final_attempt,
            "analysis": attempt_analysis,
            "progress_update": {
                "initial_attempt": initial_attempt,
                "initial_analysis": initial_attempt_analysis,
                "score_diff": score_diff,
                "feedback_diff": feedback_diff,
            },

        }


# async def translate_voice_attempt(attempt_id: int, db: Session) -> dict[str, Any]:

#     while True:

#         job_data = redis_client.blpop(queue_name, timeout=30)
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
