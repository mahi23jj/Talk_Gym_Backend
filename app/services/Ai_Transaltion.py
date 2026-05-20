# import os
# import re
# import tempfile
# from typing import Any, Dict, List, Optional

# from fastapi import UploadFile

# from imageio_ffmpeg import get_ffmpeg_exe


# ffmpeg_exe = get_ffmpeg_exe()
# os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_exe
# os.environ["FFMPEG_BINARY"] = ffmpeg_exe

# WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny")
# _model: Optional[object] = None


# def _get_model() -> object:
#     global _model
#     if _model is None:
#         try:
#             import whisper  # Local import avoids hard startup dependency in API container.
#         except ImportError as exc:
#             raise RuntimeError(
#                 "Whisper is not installed in this container. "
#                 "Install openai-whisper in requirements for this service."
#             ) from exc

#         print(f"Loading Whisper model: {WHISPER_MODEL}")
#         _model = whisper.load_model(WHISPER_MODEL)
#     return _model


# def _transcribe(source: str) -> str:
#     model = _get_model()
#     print(f"Transcribing audio from source: {source}")
#     result = model.transcribe(
#         source,
#         language="en",
#         fp16=False,
#     )
#     return result["text"]


# async def transcribe_audio(file: UploadFile) -> str:
#     with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
#         tmp.write(await file.read())
#         tmp_path = tmp.name

#     try:
#         return _transcribe(tmp_path)
#     finally:
#         if os.path.exists(tmp_path):
#             os.remove(tmp_path)


# def transcribe_audio_path(path_or_url: str) -> List[Dict[str, Any]]:
#     transcription_text = _transcribe(path_or_url)
#     return prepare_text(transcription_text)


# def split_sentences(text: str) -> List[str]:
#     return [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]

# def prepare_text(transcribe: str) -> List[Dict[str, Any]]:
#     result: List[Dict[str, Any]] = []
#     sentences = split_sentences(transcribe)

#     for idx, sentence in enumerate(sentences):
#         clean_sentence = sentence.strip()
#         result.append(
#             {
#                 "idx": idx,
#                 "sentence": clean_sentence,
#             }
#         )

#     return result
        

# import os
# import re
# import tempfile
# from typing import Dict, List

# from fastapi import UploadFile
# from groq import Groq


# client = Groq(
#     api_key=os.getenv("GROQ_API_KEY")
# )

# MODEL = "whisper-large-v3"


# def _transcribe(source: str) -> str:
#     with open(source, "rb") as audio_file:
#         transcription = client.audio.transcriptions.create(
#             file=audio_file,
#             model=MODEL,
#             response_format="text",
#             language="en",
#         )

#     return transcription.strip()


# async def transcribe_audio(file: UploadFile) -> str:
#     suffix = ".mp3"

#     if file.filename:
#         _, ext = os.path.splitext(file.filename)
#         if ext:
#             suffix = ext

#     with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
#         tmp.write(await file.read())
#         tmp_path = tmp.name

#     try:
#         return _transcribe(tmp_path)

#     finally:
#         if os.path.exists(tmp_path):
#             os.remove(tmp_path)


# def transcribe_audio_path(path_or_url: str) -> List[Dict]:
#     transcription_text = _transcribe(path_or_url)
#     return prepare_text(transcription_text)


# def split_sentences(text: str) -> List[str]:
#     return [
#         s.strip()
#         for s in re.split(r"[.!?]+", text)
#         if s.strip()
#     ]


# def prepare_text(transcribe: str) -> List[Dict]:
#     return [
#         {
#             "idx": idx,
#             "sentence": sentence.strip(),
#         }
#         for idx, sentence in enumerate(
#             split_sentences(transcribe)
#         )
#     ]
         
         


import os
import re
import tempfile
from typing import Any, Dict, List, Optional

from fastapi import UploadFile
from imageio_ffmpeg import get_ffmpeg_exe


# Configure ffmpeg
ffmpeg_exe = get_ffmpeg_exe()
os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_exe
os.environ["FFMPEG_BINARY"] = ffmpeg_exe


WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny")

_model: Optional[Any] = None


def _get_model() -> Any:
    global _model

    if _model is None:
        print(f"Loading Faster-Whisper model: {WHISPER_MODEL}")

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed in this environment. "
                "Install it in the API environment before transcribing audio."
            ) from exc

        _model = WhisperModel(
            WHISPER_MODEL,
            device="cpu",
            compute_type="int8",  # best for Render free CPU
        )

    return _model


def _transcribe(source: str) -> str:
    model = _get_model()

    print(f"Transcribing audio from source: {source}")

    segments, _ = model.transcribe(
        source,
        language="en",
    )

    text = " ".join(segment.text for segment in segments)

    return text.strip()


async def transcribe_audio(file: UploadFile) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        return _transcribe(tmp_path)

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def transcribe_audio_path(path_or_url: str) -> List[Dict[str, Any]]:
    transcription_text = _transcribe(path_or_url)
    return prepare_text(transcription_text)


def split_sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]


def prepare_text(transcribe: str) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []

    sentences = split_sentences(transcribe)

    for idx, sentence in enumerate(sentences):
        result.append(
            {
                "idx": idx,
                "sentence": sentence.strip(),
            }
        )

    return result

