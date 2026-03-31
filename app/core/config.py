import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Talk Gym Backend")
    app_version: str = os.getenv("APP_VERSION", "1.0.0")
    api_v1_prefix: str = os.getenv("API_V1_PREFIX", "/api/v1")
    postgres_url: str | None = os.getenv("POSTGRES_URL") or os.getenv("postgres_url")


settings = Settings()
