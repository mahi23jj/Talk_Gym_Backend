from __future__ import annotations

from io import BytesIO
from pathlib import Path
import asyncio

import cloudinary.uploader


ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a"}


async def upload_audio_to_cloudinary(file_content: bytes, filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_AUDIO_EXTENSIONS:
        raise ValueError("Invalid file type. Only .mp3, .wav, .ogg, and .m4a are allowed.")

    upload_stream = BytesIO(file_content)
    upload_stream.name = filename

    # cloudinary.uploader.upload is synchronous; run it in a thread to avoid blocking
    result = await asyncio.to_thread(
        cloudinary.uploader.upload, upload_stream, resource_type="video"
    )

    # size of the uploaded file in bytes    file_size = result.get("bytes", 0)
    print(f"Uploaded file size: {result.get('bytes', 0)} bytes")


    return {
        "url": result.get("secure_url"),
        "size": result.get("bytes", 0),
    }
