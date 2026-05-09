from app.core.config import settings
import redis
import redis.asyncio as async_redis


redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    username=settings.redis_username,
    password=settings.redis_password,
)

async_redis_client = async_redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    username=settings.redis_username,
    password=settings.redis_password,
)

TRANSCRIPTION_QUEUE = "transcription_queue"
ANALYSIS_QUEUE = "analysis_queue"



