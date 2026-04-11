import whisper
import tempfile
from fastapi import UploadFile

# load model ONCE (important for performance)
model = whisper.load_model("small")  # tiny / base / small / medium


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
