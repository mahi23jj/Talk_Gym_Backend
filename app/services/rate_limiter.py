# from __future__ import annotations

# from datetime import datetime, timedelta, timezone

# from fastapi import HTTPException, status
# from sqlalchemy import func
# from sqlmodel import Session, select

# from app.models.request_log import RequestLog


# async def enforce_rate_limit(
#     db: Session,
#     user_id: int,
#     endpoint: str,
#     minute_limit: int,
#     hour_limit: int,
# ) -> None:
#     now = datetime.now(timezone.utc)
#     minute_window = now - timedelta(seconds=60)
#     hour_window = now - timedelta(seconds=3600)

#     minute_count = db.exec(
#         select(func.count(RequestLog.id)).where(
#             RequestLog.user_id == user_id,
#             RequestLog.timestamp >= minute_window,
#         )
#     ).one()

#     hour_count = db.exec(
#         select(func.count(RequestLog.id)).where(
#             RequestLog.user_id == user_id,
#             RequestLog.timestamp >= hour_window,
#         )
#     ).one()

#     if int(minute_count) >= minute_limit:
#         raise HTTPException(
#             status_code=status.HTTP_429_TOO_MANY_REQUESTS,
#             detail="Rate limit exceeded: too many requests in the last minute",
#         )

#     if int(hour_count) >= hour_limit:
#         raise HTTPException(
#             status_code=status.HTTP_429_TOO_MANY_REQUESTS,
#             detail="Rate limit exceeded: too many requests in the last hour",
#         )

#     db.add(RequestLog(user_id=user_id, endpoint=endpoint))
#     db.commit()


import redis.asyncio as redis
from typing import Optional, Dict
import time

class RedisTokenBucketRateLimiter:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def enforce_rate_limit(
        self,
        user_id: int,
        endpoint: str,
        minute_limit: int,  # tokens per minute
        hour_limit: int,    # tokens per hour (fallback)
        cost: int = 1,      # cost per request
        user_tier: str = "free"  # free, premium, enterprise
    ) -> None:
        
        # Different limits per tier
        limits = self._get_limits_by_tier(user_tier, minute_limit, hour_limit)
        
        # Create unique key for this user+endpoint
        key = f"ratelimit:{user_id}:{endpoint}"
        
        # Lua script for atomic token bucket
        lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local minute_limit = tonumber(ARGV[2])
        local hour_limit = tonumber(ARGV[3])
        local cost = tonumber(ARGV[4])
        
        -- Get current bucket state
        local minute_tokens = redis.call('hget', key, 'minute_tokens')
        local minute_last = redis.call('hget', key, 'minute_last')
        local hour_tokens = redis.call('hget', key, 'hour_tokens')
        local hour_last = redis.call('hget', key, 'hour_last')
        
        -- Initialize if not exists
        if not minute_tokens then
            minute_tokens = minute_limit
            minute_last = now
            hour_tokens = hour_limit
            hour_last = now
        end
        
        -- Refill minute bucket
        local minute_elapsed = now - minute_last
        local minute_refill = minute_elapsed * (minute_limit / 60)
        minute_tokens = math.min(minute_limit, minute_tokens + minute_refill)
        
        -- Refill hour bucket
        local hour_elapsed = now - hour_last
        local hour_refill = hour_elapsed * (hour_limit / 3600)
        hour_tokens = math.min(hour_limit, hour_tokens + hour_refill)
        
        -- Check if we have enough tokens
        if minute_tokens >= cost and hour_tokens >= cost then
            minute_tokens = minute_tokens - cost
            hour_tokens = hour_tokens - cost
            
            redis.call('hset', key, 
                'minute_tokens', minute_tokens,
                'minute_last', now,
                'hour_tokens', hour_tokens,
                'hour_last', now
            )
            redis.call('expire', key, 3600)  -- Auto-cleanup after 1 hour
            
            return {1, minute_tokens, hour_tokens}
        else
            return {0, minute_tokens, hour_tokens}
        end
        """
        
        result = await self.redis.eval(
            lua_script,
            1,  # number of keys
            key,  # KEYS[1]
            time.time(),  # ARGV[1]
            limits['minute'],  # ARGV[2]
            limits['hour'],  # ARGV[3]
            cost  # ARGV[4]
        )
        
        if result[0] == 0:
            minute_remaining = int(result[1])
            hour_remaining = int(result[2])
            
            # Calculate when user can retry
            retry_after = self._calculate_retry_after(minute_remaining, limits['minute'])
            
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "retry_after_seconds": retry_after,
                    "remaining_minute_tokens": minute_remaining,
                    "remaining_hour_tokens": hour_remaining,
                    "upgrade_hint": "Upgrade to premium for higher limits"
                },
                headers={"Retry-After": str(retry_after)}
            )
        
        # Success - return remaining tokens for client-side tracking
        return {
            "remaining_minute_tokens": result[1],
            "remaining_hour_tokens": result[2]
        }
    
    def _get_limits_by_tier(self, tier: str, default_minute: int, default_hour: int) -> Dict:
        multipliers = {
            "free": 1.0,
            "premium": 3.0,
            "enterprise": 10.0
        }
        multiplier = multipliers.get(tier, 1.0)
        
        return {
            "minute": int(default_minute * multiplier),
            "hour": int(default_hour * multiplier)
        }
    
    def _calculate_retry_after(self, remaining_tokens: int, limit: int) -> int:
        """Calculate seconds until next token is available"""
        if remaining_tokens <= 0:
            # Need to wait for a full refill window
            return 60  # worst case: 1 minute
        return 1  # one token refills quickly