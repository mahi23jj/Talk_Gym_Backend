from __future__ import annotations

import asyncio
import logging
import time


from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlmodel import or_, select






from app.core.config import settings
from app.db.postgran import get_session
from app.models.auth import User
from app.models.interview import Attempt, InterviewSession
from app.schemas.interview import AttemptSubmitSchema
from app.schemas.workflow import (
    AttemptEnqueueResponse,
    AttemptResultResponse,
    FinalAttemptSubmitResponse,
)
from app.services.auth import get_current_user_id
from app.services.final_interview import get_session_result as get_final_attempt_result
from app.services.final_interview import submit_final_attempt
from app.services.interview import (
    get_analysis_result,
    get_attempt_result,
    submit_normal_attempt,
)
from app.services.rate_limiter import FastRateLimiter
from app.services.storage_validator import validate_audio_constraints
from fastapi import BackgroundTasks

router = APIRouter(prefix="/attempt", tags=["Attempt"])


# @router.post("/submit/{question_id}", response_model=AttemptEnqueueResponse)
# async def submit_attempt(
#     question_id: int,
#     data: AttemptSubmitSchema,
#     current_user: dict = Depends(get_current_user_id),
#     db=Depends(get_session),
# ):
#     request_start = time.perf_counter()
    
#     # STAGE 1: User lookup (with cache + executor to avoid blocking event loop)
#     stage_start = time.perf_counter()
    
#     # Check cache first
#     cache_key = f"{current_user['email']}|{current_user['username']}"
#     now = time.time()
#     if cache_key in _user_cache and _user_cache_ttl.get(cache_key, 0) > now:
#         user = _user_cache[cache_key]
#         print(f"[TIMING] User lookup (cached): {(time.perf_counter() - stage_start) * 1000:.2f}ms")
#     else:
#         # Run blocking DB call in thread pool
#         def _db_lookup():
#             return db.exec(
#                 select(User).where(
#                     or_(
#                         User.email == current_user["email"],
#                         User.username == current_user["username"],
#                     )
#                 )
#             ).first()
        
#         loop = asyncio.get_event_loop()
#         user = await loop.run_in_executor(_executor, _db_lookup)
#         # Cache for 60 seconds
#         _user_cache[cache_key] = user
#         _user_cache_ttl[cache_key] = now + 60
#         user_lookup_ms = (time.perf_counter() - stage_start) * 1000
#         print(f"[TIMING] User lookup (db): {user_lookup_ms:.2f}ms")

#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
#         )

#     # STAGE 2: Rate limiter
#     stage_start = time.perf_counter()
#     await FastRateLimiter.enforce(
#         user_id=user.id,
#         endpoint="/api/v1/attempt/submit/{question_id}",
#         limit=5,
#     )
#     rate_limiter_ms = (time.perf_counter() - stage_start) * 1000
#     print(f"[TIMING] Rate limiter: {rate_limiter_ms:.2f}ms")

@router.post("/submit/{question_id}", response_model=AttemptEnqueueResponse)
async def submit_attempt(
    question_id: int,
    data: AttemptSubmitSchema,
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_session),
):    
    request_start = time.perf_counter()
    user_lookup_ms = 0  # Already done by get_current_user_id dependency
    
    # STAGE 1: User lookup (already done by dependency)

    # STAGE 2: Rate limiter - Now faster with pipeline
    stage_start = time.perf_counter()
    await FastRateLimiter.enforce(
        user_id=user_id,
        endpoint="/api/v1/attempt/submit/{question_id}",
        limit=5,
        window_seconds=60,
    )
    rate_limiter_ms = (time.perf_counter() - stage_start) * 1000
    print(f"[TIMING] Rate limiter: {rate_limiter_ms:.2f}ms")

    # Rest of your code remains the same...

    # STAGE 3: Size validation
    stage_start = time.perf_counter()
    if data.size_bytes > settings.max_audio_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio file size exceeds the maximum limit of {settings.max_audio_size_bytes} bytes",
        )
    size_validation_ms = (time.perf_counter() - stage_start) * 1000
    print(f"[TIMING] Size validation: {size_validation_ms:.2f}ms")

    # STAGE 4: Audio constraints validation (duration/size only - skip slow daily count check)
    stage_start = time.perf_counter()
    if data.duration_seconds > settings.max_audio_duration_seconds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio duration exceeds limit of {settings.max_audio_duration_seconds} seconds",
        )
    if data.duration_seconds <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio duration must be greater than zero",
        )
    constraints_ms = (time.perf_counter() - stage_start) * 1000
    print(f"[TIMING] Audio constraints validation: {constraints_ms:.2f}ms")

    # STAGE 5: Submit attempt
    stage_start = time.perf_counter()
    result = await submit_normal_attempt(
        db=db,
        user_id=user_id,
        question_id=question_id,
        duration_seconds=data.duration_seconds,
        size_bytes=data.size_bytes,
        audio_url=data.audio_url,
    )
    submit_ms = (time.perf_counter() - stage_start) * 1000
    print(f"[TIMING] Submit attempt: {submit_ms:.2f}ms")
    total_ms = (time.perf_counter() - request_start) * 1000
    print(f"[TIMING] Total request: {total_ms:.2f}ms | Breakdown: user={user_lookup_ms:.2f}ms, rate_limit={rate_limiter_ms:.2f}ms, size_validation={size_validation_ms:.2f}ms, constraints={constraints_ms:.2f}ms, submit={submit_ms:.2f}ms")

    return result

# response_model=FinalAttemptSubmitResponse
@router.post("/submit/final/{attempt_id}")
async def submit_final_attempt_route(
    attempt_id: int,
    data: AttemptSubmitSchema,
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_session),
):
   
    # attempt = db.get(Attempt, attempt_id)
    # if not attempt:
    #     raise HTTPException(
    #         status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found"
    #     )
    # if attempt.user_id != user_id:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Attempt does not belong to user",
    #     )

    await FastRateLimiter.enforce(
        user_id=user_id,
        endpoint="/api/v1/attempt/submit/final/{attempt_id}",
        limit=5,
        window_seconds=60,
    )

    # await validate_audio_constraints(
    #     db=db,
    #     user_id=user_id,
    #     size_bytes=size_bytes,
    #     duration_seconds=duration_seconds,
    #     max_size_bytes=settings.max_audio_size_bytes,
    #     max_duration_seconds=settings.max_audio_duration_seconds,
    #     daily_upload_limit=40,
    # )

    if data.duration_seconds > settings.max_audio_duration_seconds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio duration exceeds limit of {settings.max_audio_duration_seconds} seconds",
        )
    if data.duration_seconds <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio duration must be greater than zero",
        )

    return await submit_final_attempt(
        db=db,
        attempt_id=attempt_id,
        audio_url=data.audio_url,
        duration_seconds=data.duration_seconds,
        size_bytes=data.size_bytes,
    )


@router.get("/result/{job_id}", response_model=AttemptResultResponse)
async def get_attempt_by_job_id(
    job_id: int,
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_session),
):
    # user = db.get(User, user_id)
    # if not user:
    #     raise HTTPException(
    #         status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
    #     )

    return await get_attempt_result(db=db, job_id=job_id)


@router.get("/analysis/{job_id}")
async def get_attempt_analysis(
    job_id: int,
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_session),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return await get_analysis_result(db=db, job_id=job_id)


@router.get("/result/final/{session_id}")
async def get_final_attempt_by_job_id(
    session_id: int,
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_session),
):

    return await get_final_attempt_result(db=db, session_id=session_id)
