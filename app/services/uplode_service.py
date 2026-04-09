from __future__ import annotations

from io import BytesIO
from pathlib import Path

import cloudinary.uploader


ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a"}


def upload_audio_to_cloudinary(file_content: bytes, filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_AUDIO_EXTENSIONS:
        raise ValueError("Invalid file type. Only .mp3, .wav, .ogg, and .m4a are allowed.")

    upload_stream = BytesIO(file_content)
    upload_stream.name = filename

    result = cloudinary.uploader.upload(upload_stream, resource_type="video")

    return result["secure_url"]
