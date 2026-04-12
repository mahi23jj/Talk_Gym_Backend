from app.core.config import Settings
import redis


redis_client = redis.Redis(host=Settings.redis_host, port=Settings.redis_port, db=Settings.redis_db)

queue_name = "audio_upload_queue"

