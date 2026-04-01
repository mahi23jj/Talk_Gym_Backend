from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from app.models.request_log import RequestLog


async def enforce_rate_limit(
    db: Session,
    user_id: int,
    endpoint: str,
    minute_limit: int,
    hour_limit: int,
) -> None:
    now = datetime.now(timezone.utc)
    minute_window = now - timedelta(seconds=60)
    hour_window = now - timedelta(seconds=3600)

    minute_count = db.exec(
        select(func.count(RequestLog.id)).where(
            RequestLog.user_id == user_id,
            RequestLog.timestamp >= minute_window,
        )
    ).one()

    hour_count = db.exec(
        select(func.count(RequestLog.id)).where(
            RequestLog.user_id == user_id,
            RequestLog.timestamp >= hour_window,
        )
    ).one()

    if int(minute_count) >= minute_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded: too many requests in the last minute",
        )

    if int(hour_count) >= hour_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded: too many requests in the last hour",
        )

    db.add(RequestLog(user_id=user_id, endpoint=endpoint))
    db.commit()
