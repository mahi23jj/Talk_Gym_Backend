import os

import cloudinary.uploader
def upload_audio_to_cloudinary(file_path: str ) -> str:
    # limit file size to 10MB
    if file_path and file_path.endswith((".mp3", ".wav", ".ogg")):
        file_size = os.path.getsize(file_path)

        # if attempt_type == "speed" and file_size > 5 * 1024 * 1024:  # 5MB for speed attempts
        #     raise ValueError("File size exceeds the 5MB limit for speed attempts")
        # elif attempt_type == "concise" and file_size > 2 * 1024 * 1024:  # 2MB for concise attempts
        #     raise ValueError("File size exceeds the 2MB limit for concise attempts")
       
    else:
        raise ValueError("Invalid file type. Only .mp3, .wav, and .ogg are allowed.")

    result = cloudinary.uploader.upload(
        file_path, resource_type="video"  # IMPORTANT for audio files
    )

    return result["secure_url"]
