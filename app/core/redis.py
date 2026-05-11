from app.core.config import settings
import redis
import redis.asyncio as async_redis


redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    username=settings.redis_username,
    password=settings.redis_password,
)

# Create a single connection pool
async_redis_client = async_redis.from_url(
    f"redis://{settings.redis_username}:{settings.redis_password}@{settings.redis_host}:{settings.redis_port}",
    decode_responses=True,
    max_connections=20,
    socket_connect_timeout=1,
    socket_timeout=1,
)

TRANSCRIPTION_QUEUE = "transcription_queue"
ANALYSIS_QUEUE = "analysis_queue"



