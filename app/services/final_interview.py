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

from app.core.redis import async_redis_client, TRANSCRIPTION 


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

async def get_session_result(
    db: Session,
    session_id: int,
) -> dict[str, Any]:

    # session_entry = db.get(
    #     InterviewSession,
    #     session_id,
    # )

    # if not session_entry:
    #     raise HTTPException(
    #         status_code=404,
    #         detail="Interview session not found",
    #     )
    
    cached = await async_redis_client.get(
        f"session_result:{session_id}"
    )

    if cached:
        return json.loads(cached)

    return {
        "status": "processing",
        "message": "Finalizing analysis..."
       }

    """  attempts = db.exec(
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
    ) """

async def submit_final_attempt(
    db: Session,
    attempt_id: int,
    audio_url: str,
    duration_seconds: int,
    size_bytes: int,
) -> dict[str, Any]:

    job_entry = db.get(Job, attempt_id)
    if not job_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="job not found"
        )

    attempt = db.get(Attempt, job_entry.attempt_id)
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

     # Pipeline Redis operations
    pipeline = async_redis_client.pipeline()
    pipeline.rpush(TRANSCRIPTION, json.dumps(payload))
    await pipeline.execute()
    
        
    db.commit()
      
    return {
        "job_id": job_entry.id,
        "session_id": attempt.session_id,
        "message": "Attempt submitted successfully and is being processed.",
    }


