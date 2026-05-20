from __future__ import annotations

# import math
# import re
# from typing import Any, TypedDict

# import librosa
# import logging
# import numpy as np
# import requests
# import tempfile
# import os
# from urllib.parse import urlparse


# class PauseMetrics(TypedDict):
#     average_duration: float
#     long_pause_count: int
#     pause_frequency: float
#     silence_ratio: float


# class PitchMetrics(TypedDict):
#     mean: float
#     variance: float
#     monotony_score: float


# class VoiceMetrics(TypedDict):
#     confidence: float
#     speech_rate: float
#     nervousness: float
#     pauses: PauseMetrics
#     pitch: PitchMetrics


# TARGET_SAMPLE_RATE = 16000
# PAUSE_TOP_DB = 30
# LONG_PAUSE_THRESHOLD_SECONDS = 0.6
# IDEAL_SPEECH_RATE = 1.8
# IDEAL_SPEECH_RATE_TOLERANCE = 0.8


# def _clamp(value: float, minimum: float = 0.0, maximum: float = 10.0) -> float:
#     return max(minimum, min(maximum, value))


# def _safe_mean(values: np.ndarray) -> float:
#     if values.size == 0:
#         return 0.0
#     return float(np.mean(values))


# def _safe_variance(values: np.ndarray) -> float:
#     if values.size == 0:
#         return 0.0
#     return float(np.var(values))


# def _safe_word_count(text: str) -> int:
#     return len(re.findall(r"\b\w+\b", text))


# def _coefficient_of_variation(values: np.ndarray) -> float:
#     if values.size < 2:
#         return 0.0

#     mean_value = float(np.mean(values))
#     if abs(mean_value) < 1e-8:
#         return 0.0

#     return float(np.std(values) / abs(mean_value))


# def _load_audio(audio_path: str) -> tuple[np.ndarray, int]:
#     # If audio_path is a remote URL, download to a temp file first
#     is_url = isinstance(audio_path, str) and audio_path.startswith(("http://", "https://"))
#     tmp_path = None
#     try:
#         logger = logging.getLogger(__name__)
#         if is_url:
#             logger.info("Downloading remote audio for analysis: %s", audio_path)
#         if is_url:
#             resp = requests.get(audio_path, stream=True, timeout=30)
#             resp.raise_for_status()
#             suffix = os.path.splitext(urlparse(audio_path).path)[1] or ".mp4"
#             with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
#                 for chunk in resp.iter_content(chunk_size=8192):
#                     if chunk:
#                         tmp.write(chunk)
#                 tmp_path = tmp.name

#             load_path = tmp_path
#         else:
#             load_path = audio_path

#         y, sr = librosa.load(load_path, sr=TARGET_SAMPLE_RATE, mono=True)
#         logger.info("Loaded audio (%s) sample rate=%s, frames=%s", load_path, sr, len(y))
#         return y.astype(np.float32), int(sr)
#     finally:
#         if tmp_path and os.path.exists(tmp_path):
#             try:
#                 os.unlink(tmp_path)
#             except Exception:
#                 pass


# def extract_voice_features(audio_path: str) -> dict[str, Any]:
#     logger = logging.getLogger(__name__)
#     logger.info("Starting voice feature extraction for: %s", audio_path)
#     y, sr = _load_audio(audio_path)

#     duration_seconds = float(len(y) / sr) if sr else 0.0
#     if duration_seconds <= 0:
#         raise ValueError("Audio duration must be greater than zero")

#     intervals = librosa.effects.split(y, top_db=PAUSE_TOP_DB)

#     pause_durations: list[float] = []
#     speech_segments_seconds = 0.0

#     if len(intervals) > 0:
#         for start, end in intervals:
#             speech_segments_seconds += float(end - start) / sr

#         for index in range(1, len(intervals)):
#             previous_end = intervals[index - 1][1]
#             current_start = intervals[index][0]
#             pause_duration = max(0.0, float(current_start - previous_end) / sr)
#             if pause_duration > 0:
#                 pause_durations.append(pause_duration)

#     average_pause_duration = float(np.mean(pause_durations)) if pause_durations else 0.0
#     long_pause_count = sum(
#         1 for pause in pause_durations if pause >= LONG_PAUSE_THRESHOLD_SECONDS
#     )
#     pause_frequency = float(len(pause_durations) / duration_seconds)
#     silence_ratio = float(
#         np.clip((duration_seconds - speech_segments_seconds) / duration_seconds, 0.0, 1.0)
#     )

#     rms_energy = librosa.feature.rms(y=y)[0]
#     avg_energy = _safe_mean(rms_energy)
#     energy_variance = _safe_variance(rms_energy)

#     try:
#         pitch_track = librosa.yin(y, fmin=75, fmax=300, sr=sr)
#         pitch_track = pitch_track[np.isfinite(pitch_track) & (pitch_track > 0)]
#     except Exception:
#         pitch_track = np.array([])

#     pitch_mean = _safe_mean(pitch_track)
#     pitch_variance = _safe_variance(pitch_track)

#     pitch_std = float(np.sqrt(pitch_variance))
#     pitch_norm = pitch_std / max(pitch_mean, 1.0)
#     monotony_score = _clamp(10.0 - pitch_norm * 12.0)

#     pause_series = np.asarray(pause_durations, dtype=np.float32)
#     pause_irregularity = _coefficient_of_variation(pause_series)
#     energy_irregularity = _coefficient_of_variation(rms_energy)

#     result = {
#         "duration_seconds": duration_seconds,
#         "avg_energy": avg_energy,
#         "energy_variance": energy_variance,
#         "pause_irregularity": pause_irregularity,
#         "energy_irregularity": energy_irregularity,
#         "pauses": {
#             "average_duration": average_pause_duration,
#             "long_pause_count": long_pause_count,
#             "pause_frequency": pause_frequency,
#             "silence_ratio": silence_ratio,
#         },
#         "pitch": {
#             "mean": pitch_mean,
#             "variance": pitch_variance,
#             "monotony_score": monotony_score,
#         },
#     }

#     logger.info("Completed voice feature extraction for %s: duration=%.2fs, pauses=%s", audio_path, duration_seconds, len(pause_durations))
#     return result


# def build_voice_metrics(
#     raw_features: dict[str, Any],
#     transcript: Any = None,
#     duration_seconds: float | None = None,
# ) -> VoiceMetrics:
#     pauses: dict[str, Any] = dict(raw_features.get("pauses", {}))
#     pitch: dict[str, Any] = dict(raw_features.get("pitch", {}))

#     effective_duration = float(
#         duration_seconds if duration_seconds is not None else raw_features.get("duration_seconds", 0.0)
#     )
#     if effective_duration <= 0:
#         effective_duration = 1.0

#     transcript_text = ""
#     if isinstance(transcript, list):
#         transcript_text = " ".join(
#             str(item.get("sentence", "")).strip()
#             for item in transcript
#             if isinstance(item, dict)
#         ).strip()
#     elif transcript is not None:
#         transcript_text = str(transcript).strip()

#     word_count = _safe_word_count(transcript_text)
#     speech_rate = float(word_count / effective_duration)

#     average_pause_duration = float(pauses.get("average_duration", 0.0))
#     long_pause_count = int(pauses.get("long_pause_count", 0))
#     pause_frequency = float(pauses.get("pause_frequency", 0.0))
#     silence_ratio = float(pauses.get("silence_ratio", 0.0))

#     pitch_mean = float(pitch.get("mean", 0.0))
#     pitch_variance = float(pitch.get("variance", 0.0))
#     monotony_score = float(pitch.get("monotony_score", 0.0))

#     pause_pressure = (
#         min(4.0, average_pause_duration * 2.0)
#         + min(2.0, long_pause_count * 0.45)
#         + min(2.5, silence_ratio * 4.0)
#         + min(1.5, max(0.0, pause_frequency - 0.25) * 2.0)
#     )

#     speech_rate_distance = abs(speech_rate - IDEAL_SPEECH_RATE)
#     speech_rate_pressure = min(
#         2.5,
#         (speech_rate_distance / IDEAL_SPEECH_RATE_TOLERANCE) * 1.8,
#     )

#     pitch_instability = 0.0
#     if pitch_mean > 0:
#         pitch_instability = min(2.5, (math.sqrt(pitch_variance) / pitch_mean) * 6.0)

#     energy_irregularity = float(raw_features.get("energy_irregularity", 0.0))
#     energy_pressure = min(2.0, energy_irregularity * 2.5)

#     nervousness = _clamp(
#         1.5
#         + pause_pressure * 0.75
#         + speech_rate_pressure * 0.7
#         + pitch_instability * 0.6
#         + energy_pressure * 0.4,
#     )

#     pacing_bonus = 0.0
#     if 1.0 <= speech_rate <= 2.4:
#         pacing_bonus = 1.0
#     elif 0.8 <= speech_rate <= 2.8:
#         pacing_bonus = 0.4

#     confidence = _clamp(
#         8.5
#         - pause_pressure * 0.9
#         - nervousness * 0.45
#         + pacing_bonus
#         + min(0.8, raw_features.get("avg_energy", 0.0) * 8.0),
#     )

#     return {
#         "confidence": round(confidence, 2),
#         "speech_rate": round(speech_rate, 2),
#         "nervousness": round(nervousness, 2),
#         "pauses": {
#             "average_duration": round(average_pause_duration, 3),
#             "long_pause_count": long_pause_count,
#             "pause_frequency": round(pause_frequency, 3),
#             "silence_ratio": round(silence_ratio, 3),
#         },
#         "pitch": {
#             "mean": round(pitch_mean, 3),
#             "variance": round(pitch_variance, 3),
#             "monotony_score": round(monotony_score, 2),
#         },
#     }


# def analyze_voice_metrics(
#     audio_path: str,
#     transcript: Any = None,
#     duration_seconds: float | None = None,
# ) -> VoiceMetrics:
#     raw_features = extract_voice_features(audio_path)
#     return build_voice_metrics(
#         raw_features=raw_features,
#         transcript=transcript,
#         duration_seconds=duration_seconds,
#     )

import os

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import math
import re
import json
import logging
import tempfile
import subprocess
from typing import Any, TypedDict

import numpy as np
import librosa
import requests
import os
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# =========================
# CONFIG
# =========================
TARGET_SAMPLE_RATE = 8000
PAUSE_TOP_DB = 30
LONG_PAUSE_THRESHOLD_SECONDS = 0.6
IDEAL_SPEECH_RATE = 1.8
IDEAL_SPEECH_RATE_TOLERANCE = 0.8


# =========================
# TYPES
# =========================
class PauseMetrics(TypedDict):
    average_duration: float
    long_pause_count: int
    pause_frequency: float
    silence_ratio: float


class PitchMetrics(TypedDict):
    mean: float
    variance: float
    monotony_score: float


class VoiceMetrics(TypedDict):
    confidence: float
    speech_rate: float
    nervousness: float
    pauses: PauseMetrics
    pitch: PitchMetrics


# =========================
# UTIL
# =========================
def _clamp(v: float, mn: float = 0.0, mx: float = 10.0) -> float:
    return max(mn, min(mx, v))


def _safe_mean(x: np.ndarray) -> float:
    return float(np.mean(x)) if x.size else 0.0


def _safe_var(x: np.ndarray) -> float:
    return float(np.var(x)) if x.size else 0.0


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


# =========================
# STEP 1: DOWNLOAD (CLOUDINARY SAFE)
# =========================
# def _download_to_temp(url: str) -> str:
#     logger.info("Downloading media: %s", url)

#     r = requests.get(url, stream=True, timeout=60)
#     r.raise_for_status()

#     suffix = os.path.splitext(urlparse(url).path)[1] or ".mp4"

#     tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
#     try:
#         for chunk in r.iter_content(chunk_size=1024 * 1024):
#             if chunk:
#                 tmp.write(chunk)
#     finally:
#         tmp.close()


#     return tmp.name
def _download_to_temp(url_or_path: str) -> str:
    # Already a local file — skip download entirely
    if os.path.isfile(url_or_path):
        logger.info("Using local file directly: %s", url_or_path)
        return url_or_path

    if not url_or_path.startswith(("http://", "https://")):
        raise ValueError(f"Not a valid URL or existing local path: {url_or_path!r}")

    logger.info("Downloading media: %s", url_or_path)
    r = requests.get(
        url_or_path,
        stream=True,
        timeout=60,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    r.raise_for_status()

    suffix = os.path.splitext(urlparse(url_or_path).path)[1] or ".mp4"

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                tmp.write(chunk)
    finally:
        tmp.close()

    return tmp.name


# =========================
# STEP 2: FORCE CONVERT TO WAV (IMPORTANT FIX)
# =========================
def _convert_to_wav(input_path: str) -> str:
    wav_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-ac",
        "1",
        "-ar",
        str(TARGET_SAMPLE_RATE),
        wav_path,
    ]

    logger.info("Converting to WAV via FFmpeg...")

    subprocess.run(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
    )

    return wav_path


# =========================
# STEP 3: LOAD AUDIO (ONLY WAV)
# =========================
def _load_audio(path: str):
    y, sr = librosa.load(path, sr=TARGET_SAMPLE_RATE, mono=True)
    return y.astype(np.float32), sr


# =========================
# STEP 4: FEATURE EXTRACTION (SAFE)
# =========================
def extract_voice_features(audio_url: str) -> dict[str, Any]:
    tmp_file = None
    wav_file = None

    try:
        logger.info("Starting voice analysis: %s", audio_url)

        # 1. download
        # tmp_file = _download_to_temp(audio_url)

        # 2. convert
        wav_file = _convert_to_wav(audio_url)

        # 3. load
        y, sr = _load_audio(wav_file)

        duration = len(y) / sr
        if duration <= 0:
            raise ValueError("Invalid audio duration")

        intervals = librosa.effects.split(y, top_db=PAUSE_TOP_DB)

        pause_durations = []
        speech_time = 0.0

        for start, end in intervals:
            speech_time += (end - start) / sr

        for i in range(1, len(intervals)):
            pause = (intervals[i][0] - intervals[i - 1][1]) / sr
            if pause > 0:
                pause_durations.append(pause)

        avg_pause = float(np.mean(pause_durations)) if pause_durations else 0.0
        long_pauses = sum(p >= LONG_PAUSE_THRESHOLD_SECONDS for p in pause_durations)
        silence_ratio = (duration - speech_time) / duration if duration else 0

        rms = librosa.feature.rms(y=y)[0]

        # ❗ FIXED: NO fill_na in modern librosa
        try:
            # pitch = librosa.yin(y, fmin=75, fmax=300, sr=sr)
            pitch = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            pitch = pitch[np.isfinite(pitch)]
        except Exception:
            pitch = np.array([])

        pitch_mean = _safe_mean(pitch)
        pitch_var = _safe_var(pitch)

        return {
            "duration_seconds": duration,
            "avg_energy": float(np.mean(rms)) if len(rms) else 0.0,
            "energy_variance": float(np.var(rms)) if len(rms) else 0.0,
            "pauses": {
                "average_duration": avg_pause,
                "long_pause_count": int(long_pauses),
                "pause_frequency": len(pause_durations) / duration if duration else 0,
                "silence_ratio": float(np.clip(silence_ratio, 0, 1)),
            },
            "pitch": {
                "mean": pitch_mean,
                "variance": pitch_var,
                "monotony_score": float(
                    max(0, 10 - np.std(pitch) if len(pitch) else 5)
                ),
            },
        }

    except Exception as e:
        logger.exception("Voice analysis failed: %s", e)
        raise RuntimeError(f"Voice analysis failed: {e}")

    finally:
        for f in [tmp_file, wav_file]:
            if f and os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass


# =========================
# STEP 5: SAFE METRICS BUILDER
# =========================


def _label_score(score: float) -> str:
    if score >= 8:
        return "Excellent"
    if score >= 6:
        return "Good"
    if score >= 4:
        return "Average"
    return "Needs Improvement"


def _speech_rate_feedback(rate: float) -> tuple[str, str]:
    if rate < 1.2:
        return "Too Slow", "Try speaking a little faster to sound more natural."
    if rate <= 2.6:
        return "Natural Pace", "Your speaking speed sounds balanced."
    if rate <= 3.5:
        return "Slightly Fast", "Slow down slightly for better clarity."
    return "Too Fast", "You’re rushing. Pause more between ideas."


def _nervousness_feedback(score: float) -> tuple[str, str]:
    if score <= 3:
        return "Calm", "You sound relaxed and controlled."
    if score <= 6:
        return "Slight Tension", "Some minor nervousness detected."
    if score <= 8:
        return "Noticeable Nervousness", "Practice pacing and breathing."
    return "High Nervousness", "Frequent pauses suggest stress."


def _pitch_feedback(monotony: float) -> tuple[str, str]:
    if monotony >= 8:
        return "Very Expressive", "Strong vocal variation."
    if monotony >= 5:
        return "Natural Variation", "Healthy pitch dynamics."
    if monotony >= 3:
        return "Slightly Flat", "Add more vocal emphasis."
    return "Monotone", "Your voice lacks variation."


def build_voice_metrics(
    raw_features: dict[str, Any],
    transcript: Any = None,
    duration_seconds: float | None = None,
) -> dict[str, Any]:

    pauses = raw_features.get("pauses", {})
    pitch = raw_features.get("pitch", {})

    duration = duration_seconds or raw_features.get("duration_seconds", 1.0)
    duration = max(duration, 1.0)

    text = ""
    if isinstance(transcript, list):
        text = " ".join(t.get("sentence", "") for t in transcript)
    elif transcript:
        text = str(transcript)

    words = len(text.split())
    speech_rate = words / duration

    avg_pause = pauses.get("average_duration", 0)
    long_pauses = pauses.get("long_pause_count", 0)
    silence_ratio = pauses.get("silence_ratio", 0)

    nervousness = min(
        10,
        1.5 + avg_pause * 2 + long_pauses * 0.5 + silence_ratio * 3,
    )

    confidence = max(0, 10 - nervousness)

    monotony_score = pitch.get("monotony_score", 0)

    pace_label, pace_tip = _speech_rate_feedback(speech_rate)
    nerve_label, nerve_tip = _nervousness_feedback(nervousness)
    pitch_label, pitch_tip = _pitch_feedback(monotony_score)

    return {
        "confidence": {
            "score": round(confidence, 1),
            "level": _label_score(confidence),
        },
        "delivery": {
            "speech_rate_wps": round(speech_rate, 2),
            "pace": pace_label,
            "tip": pace_tip,
        },
        "nervousness": {
            "score": round(nervousness, 1),
            "level": nerve_label,
            "tip": nerve_tip,
        },
        "voice_tone": {
            "variation_score": round(monotony_score, 1),
            "level": pitch_label,
            "tip": pitch_tip,
        },
        "pausing": {
            "average_pause_seconds": round(avg_pause, 2),
            "long_pauses": long_pauses,
            "silence_percent": round(silence_ratio * 100, 1),
        },
        "summary": (
            f"{_label_score(confidence)} confidence, "
            f"{pace_label.lower()}, "
            f"{pitch_label.lower()}, "
            f"{nerve_label.lower()}."
        ),
    }


# =========================
# ENTRY
# =========================
def analyze_voice_metrics(audio_url: str, transcript=None):
    raw = extract_voice_features(audio_url)
    return build_voice_metrics(raw, transcript)
