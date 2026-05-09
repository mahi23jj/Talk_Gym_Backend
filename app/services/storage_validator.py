from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from app.models.recording import Recording

logger = logging.getLogger(__name__)


async def validate_audio_constraints(
    db: Session,
    user_id: int,
    size_bytes: int,
    duration_seconds: int,
    max_size_bytes: int,
    max_duration_seconds: int,
    daily_upload_limit: int,
) -> None:
    fn_start = time.perf_counter()
    
    # Quick validations
    quick_start = time.perf_counter()
    if size_bytes > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds limit of {max_size_bytes} bytes",
        )

    if duration_seconds > max_duration_seconds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio duration exceeds limit of {max_duration_seconds} seconds",
        )

    if duration_seconds <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio duration must be greater than zero",
        )
    quick_ms = (time.perf_counter() - quick_start) * 1000
    print(f"[TIMING:validate_audio_constraints] Quick validations: {quick_ms:.2f}ms")

    # Daily upload count check
    daily_check_start = time.perf_counter()
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    daily_count = db.exec(
        select(func.count(Recording.id)).where(
            Recording.user_id == user_id,
            Recording.created_at >= start_of_day,
            Recording.created_at < end_of_day,
        )
    ).one()
    daily_check_ms = (time.perf_counter() - daily_check_start) * 1000
    print(f"[TIMING:validate_audio_constraints] Daily count query: {daily_check_ms:.2f}ms, count={daily_count}")

    if int(daily_count) >= daily_upload_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily upload limit exceeded",
        )
    
    total_fn_ms = (time.perf_counter() - fn_start) * 1000
    logger.info(f"[TIMING:validate_audio_constraints] TOTAL: {total_fn_ms:.2f}ms")
    raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily upload limit exceeded",
        )
    
    total_fn_ms = (time.perf_counter() - fn_start) * 1000
    logger.info(f"[TIMING:validate_audio_constraints] TOTAL: {total_fn_ms:.2f}ms")
