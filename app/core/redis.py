from app.core.config import settings
import redis
import redis.asyncio as async_redis


redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    username=settings.redis_username,
    password=settings.redis_password,
    decode_responses=True,
)


async_redis_client = async_redis.from_url(
    f"redis://{settings.redis_username}:{settings.redis_password}@{settings.redis_host}:{settings.redis_port}",
    decode_responses=True,
    max_connections=20,

    # FIXED
    socket_connect_timeout=30,
    socket_timeout=60,
    retry_on_timeout=True,
    health_check_interval=30,
)


TRANSCRIPTION = "TRANSCRIPTION"
ANALYSIS_QUEUE = "analysis_queue"



