from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from app.models.enums import AttemptStage
from app.models.job import Job
from app.models.interview import Attempt, InterviewAnalysis, InterviewSession
from app.models.question import Question

from app.core.redis import async_redis_client, TRANSCRIPTION_QUEUE 


from datetime import timezone
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select
from app.models.job import Job


# =========================================================
# HELPERS
# =========================================================

def safe_get(data: dict, *keys, default=None):
    current = data

    for key in keys:
        if not isinstance(current, dict):
            return default

        current = current.get(key)

        if current is None:
            return default

    return current


def calculate_trend(change: int) -> str:
    if change > 0:
        return "improved"

    if change < 0:
        return "regressed"

    return "unchanged"


def build_score_comparison(initial: int, final: int) -> dict:
    change = final - initial

    percent = 0
    if initial > 0:
        percent = round((change / initial) * 100, 1)

    return {
        "initial": initial,
        "final": final,
        "change": change,
        "change_percent": percent,
        "trend": calculate_trend(change),
    }


def extract_strengths(final_raw: dict) -> list[dict]:
    strengths = []

    clarity = safe_get(final_raw, "content", "clarity", default=0)
    ownership = safe_get(final_raw, "behavioral", "ownership", default=0)

    if clarity >= 7:
        strengths.append({
            "title": "Clear Communication",
            "description": "Your answer was easy to follow and understandable."
        })

    if ownership >= 7:
        strengths.append({
            "title": "Strong Ownership",
            "description": "You communicated personal responsibility clearly."
        })

    return strengths


def extract_weaknesses(final_raw: dict) -> list[dict]:
    weaknesses = []

    flags = final_raw.get("flags", [])

    if "no_measurable_impact" in flags:
        weaknesses.append({
            "title": "Weak Measurable Impact",
            "description": "Your answer lacks quantified outcomes and measurable achievements."
        })

    if "low_specificity" in flags:
        weaknesses.append({
            "title": "Low Specificity",
            "description": "Your examples remain too general and lack concrete details."
        })

    return weaknesses


def build_category_comparison(
    initial_raw: dict,
    final_raw: dict,
) -> dict:

    categories = {
        "clarity": (
            safe_get(initial_raw, "content", "clarity", default=0),
            safe_get(final_raw, "content", "clarity", default=0),
        ),

        "structure_star": (
            safe_get(initial_raw, "content", "structure_star", default=0),
            safe_get(final_raw, "content", "structure_star", default=0),
        ),

        "specificity": (
            safe_get(initial_raw, "content", "specificity", default=0),
            safe_get(final_raw, "content", "specificity", default=0),
        ),

        "ownership": (
            safe_get(initial_raw, "behavioral", "ownership", default=0),
            safe_get(final_raw, "behavioral", "ownership", default=0),
        ),

        "initiative": (
            safe_get(initial_raw, "behavioral", "initiative", default=0),
            safe_get(final_raw, "behavioral", "initiative", default=0),
        ),

        "impact": (
            safe_get(initial_raw, "behavioral", "impact", default=0),
            safe_get(final_raw, "behavioral", "impact", default=0),
        ),
    }

    result = {}

    for category, (initial, final) in categories.items():
        change = final - initial

        result[category] = {
            "initial": initial,
            "final": final,
            "change": change,
            "trend": calculate_trend(change),
        }

    return result


def build_improvement_sections(category_scores: dict) -> dict:
    improved = []
    unchanged = []
    regressed = []

    for skill, data in category_scores.items():

        item = {
            "skill": skill,
            "change": data["change"],
            "trend": data["trend"],
        }

        if data["trend"] == "improved":
            improved.append(item)

        elif data["trend"] == "regressed":
            regressed.append(item)

        else:
            unchanged.append(item)

    return {
        "improved_areas": improved,
        "unchanged_areas": unchanged,
        "regressed_areas": regressed,
    }


def build_sentence_feedback(final_raw: dict) -> list[dict]:
    feedback_items = []

    for item in final_raw.get("sentence_feedback", []):

        feedback_items.append({
            "sentence_index": item.get("sentence_index"),
            "original": item.get("sentence"),
            "issue": item.get("issue"),
            "improvement_type": item.get("improvement_type"),
            "improved_example": item.get("improved_example"),
        })

    return feedback_items


# =========================================================
# MAIN REPORT BUILDER
# =========================================================

def build_interview_report(
    initial_attempt: Attempt,
    final_attempt: Attempt,
    initial_analysis: InterviewAnalysis,
    final_analysis: InterviewAnalysis,
) -> dict:

    initial_raw = initial_analysis.raw_analysis_json or {}
    final_raw = final_analysis.raw_analysis_json or {}

    overall_comparison = build_score_comparison(
        initial_analysis.score,
        final_analysis.score,
    )

    category_scores = build_category_comparison(
        initial_raw,
        final_raw,
    )

    improvements = build_improvement_sections(category_scores)

    return {
        "status": "completed",

        "interview": {
            "attempt_id": final_attempt.id,
            "question_id": final_attempt.question_id,
            "stage": final_attempt.stage,
            "completed_at": final_analysis.created_at,
        },

        "performance_summary": {
            "overall_score": overall_comparison,

            "performance_level": (
                "Advanced"
                if final_analysis.score >= 8
                else "Intermediate"
                if final_analysis.score >= 5
                else "Beginner"
            ),

            "primary_improvement_area": "impact",

            "primary_strength": "clarity",
        },

        "category_scores": category_scores,

        "final_analysis": {
            "summary": final_raw.get("short_feedback"),

            "strengths": extract_strengths(final_raw),

            "weaknesses": extract_weaknesses(final_raw),

            "flags": final_raw.get("flags", []),
        },

        "improvement_analysis": improvements,

        "coaching": {
            "recommended_training_mode": final_raw.get(
                "primary_training_mode"
            ),

            "next_focus_skill": "impact",

            "coach_message": (
                "Focus on measurable outcomes and stronger STAR structure."
            ),

            "followup_questions": [
                {
                    "question": q.get("question"),
                    "target_skill": q.get("target_improvement"),
                }
                for q in final_raw.get("behavioral_questions", [])
            ],
        },

        "star_rewrite_example": {
            "situation": safe_get(final_raw, "star_example", "s"),
            "task": safe_get(final_raw, "star_example", "t"),
            "action": safe_get(final_raw, "star_example", "a"),
            "result": safe_get(final_raw, "star_example", "r"),
        },

        "sentence_feedback": build_sentence_feedback(final_raw),

        "visualization_ready": {
            "radar_scores_final": {
                "clarity": safe_get(final_raw, "content", "clarity", default=0),
                "structure_star": safe_get(final_raw, "content", "structure_star", default=0),
                "specificity": safe_get(final_raw, "content", "specificity", default=0),
                "ownership": safe_get(final_raw, "behavioral", "ownership", default=0),
                "initiative": safe_get(final_raw, "behavioral", "initiative", default=0),
                "impact": safe_get(final_raw, "behavioral", "impact", default=0),
            },

            "radar_scores_initial": {
                "clarity": safe_get(initial_raw, "content", "clarity", default=0),
                "structure_star": safe_get(initial_raw, "content", "structure_star", default=0),
                "specificity": safe_get(initial_raw, "content", "specificity", default=0),
                "ownership": safe_get(initial_raw, "behavioral", "ownership", default=0),
                "initiative": safe_get(initial_raw, "behavioral", "initiative", default=0),
                "impact": safe_get(initial_raw, "behavioral", "impact", default=0),
            },
        },
    }


# =========================================================
# ENDPOINT SERVICE
# =========================================================

def get_session_result(
    db: Session,
    session_id: int,
) -> dict[str, Any]:

    session_entry = db.get(
        InterviewSession,
        session_id,
    )

    if not session_entry:
        raise HTTPException(
            status_code=404,
            detail="Interview session not found",
        )

    attempts = db.exec(
        select(Attempt)
        .where(Attempt.session_id == session_id)
        .options(selectinload(Attempt.analysis), selectinload(Attempt.recording))
    ).all()

    initial_attempt = next(
        (
            a for a in attempts
            if a.stage == AttemptStage.INITIAL
        ),
        None,
    )

    final_attempt = next(
        (
            a for a in attempts
            if a.stage == AttemptStage.FINAL
        ),
        None,
    )

    if not initial_attempt:
        raise HTTPException(
            status_code=404,
            detail="Initial attempt not found",
        )

    if not final_attempt:
        return {
            "status": "in_progress",
            "message": "Final interview not submitted yet.",
        }

    final_job = db.exec(
        select(Job).where(
            Job.attempt_id == final_attempt.id
        )
    ).first()

    if final_job and final_job.status == "pending":
        return {
            "status": "processing",
            "message": "Final interview analysis is processing.",
        }

    if final_job and final_job.status == "failed":
        return {
            "status": "failed",
            "message": "Final interview analysis failed.",
        }

    initial_analysis = initial_attempt.analysis
    final_analysis = final_attempt.analysis

    if not initial_analysis or not final_analysis:
        raise HTTPException(
            status_code=404,
            detail="Interview analysis not found",
        )

    return build_interview_report(
        initial_attempt=initial_attempt,
        final_attempt=final_attempt,
        initial_analysis=initial_analysis,
        final_analysis=final_analysis,
    )

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
        "session_id": attempt.session_id,
    }

    async_redis_client.rpush(
        TRANSCRIPTION_QUEUE,
        json.dumps(payload),
    )
    return {
        "job_id": job_entry.id,
        "session_id": attempt.session_id,
        "message": "Attempt submitted successfully and is being processed.",
    }


# def get_attempt_result(db: Session, job_id: int, attempt_id: int) -> dict[str, Any]:
#     job_entry = db.get(Job, job_id)
#     if not job_entry:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
#         )

#     if job_entry.status == "pending":
#         return {
#             "status": "pending",
#             "message": "Your attempt is still being processed. Please check back later.",
#         }
#     elif job_entry.status == "failed":
#         return {
#             "status": "failed",
#             "message": "Processing of your attempt failed. Please try again.",
#         }
#     else:
#         initial_attempt = db.get(Attempt, attempt_id)
#         final_attempt = db.get(Attempt, job_entry.attempt_id)

#         initial_attempt_analysis = db.exec(
#             select(InterviewAnalysis).where(
#                 InterviewAnalysis.attempt_id == attempt_id
#             )
#         ).one_or_none()

#         attempt_analysis = db.exec(
#             select(InterviewAnalysis).where(
#                 InterviewAnalysis.attempt_id == job_entry.attempt_id
#             )
#         ).one_or_none()

#         score_diff = None
#         feedback_diff = None
#         if initial_attempt_analysis and attempt_analysis:
#             score_diff = attempt_analysis.score - initial_attempt_analysis.score
#             feedback_diff = (
#                 f"Initial feedback: {initial_attempt_analysis.feedback}\n"
#                 f"Final feedback: {attempt_analysis.feedback}"
#             )



#         if not attempt_analysis:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found"
#             )
        
#         return {
#             "status": "done",
#             "attempt": final_attempt,
#             "analysis": attempt_analysis,
#             "progress_update": {
#                 "initial_attempt": initial_attempt,
#                 "initial_analysis": initial_attempt_analysis,
#                 "score_diff": score_diff,
#                 "feedback_diff": feedback_diff,
#             },

#         }


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
