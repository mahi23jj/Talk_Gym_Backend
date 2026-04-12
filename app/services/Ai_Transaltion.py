import os
import whisper
import tempfile
from fastapi import UploadFile

from imageio_ffmpeg import get_ffmpeg_exe


ffmpeg_exe = get_ffmpeg_exe()
os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_exe
os.environ["FFMPEG_BINARY"] = ffmpeg_exe

# load model ONCE (important for performance)
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
print(f"Loading Whisper model: {WHISPER_MODEL}")
model = whisper.load_model(WHISPER_MODEL)


async def transcribe_audio(file: UploadFile) -> str:
    # save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    # run whisper
    result = model.transcribe(
        tmp_path,
        language="en",
        fp16=False,  # for CPU inference
    )

    return result["text"]
