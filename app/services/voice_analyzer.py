from __future__ import annotations

import math
import re
from typing import Any, TypedDict

import librosa
import numpy as np


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


TARGET_SAMPLE_RATE = 16000
PAUSE_TOP_DB = 30
LONG_PAUSE_THRESHOLD_SECONDS = 0.6
IDEAL_SPEECH_RATE = 1.8
IDEAL_SPEECH_RATE_TOLERANCE = 0.8


def _clamp(value: float, minimum: float = 0.0, maximum: float = 10.0) -> float:
    return max(minimum, min(maximum, value))


def _safe_mean(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    return float(np.mean(values))


def _safe_variance(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    return float(np.var(values))


def _safe_word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _coefficient_of_variation(values: np.ndarray) -> float:
    if values.size < 2:
        return 0.0

    mean_value = float(np.mean(values))
    if abs(mean_value) < 1e-8:
        return 0.0

    return float(np.std(values) / abs(mean_value))


def _load_audio(audio_path: str) -> tuple[np.ndarray, int]:
    y, sr = librosa.load(audio_path, sr=TARGET_SAMPLE_RATE, mono=True)
    return y.astype(np.float32), int(sr)


def extract_voice_features(audio_path: str) -> dict[str, Any]:
    y, sr = _load_audio(audio_path)

    duration_seconds = float(len(y) / sr) if sr else 0.0
    if duration_seconds <= 0:
        raise ValueError("Audio duration must be greater than zero")

    intervals = librosa.effects.split(y, top_db=PAUSE_TOP_DB)

    pause_durations: list[float] = []
    speech_segments_seconds = 0.0

    if len(intervals) > 0:
        for start, end in intervals:
            speech_segments_seconds += float(end - start) / sr

        for index in range(1, len(intervals)):
            previous_end = intervals[index - 1][1]
            current_start = intervals[index][0]
            pause_duration = max(0.0, float(current_start - previous_end) / sr)
            if pause_duration > 0:
                pause_durations.append(pause_duration)

    average_pause_duration = float(np.mean(pause_durations)) if pause_durations else 0.0
    long_pause_count = sum(
        1 for pause in pause_durations if pause >= LONG_PAUSE_THRESHOLD_SECONDS
    )
    pause_frequency = float(len(pause_durations) / duration_seconds)
    silence_ratio = float(
        np.clip((duration_seconds - speech_segments_seconds) / duration_seconds, 0.0, 1.0)
    )

    rms_energy = librosa.feature.rms(y=y)[0]
    avg_energy = _safe_mean(rms_energy)
    energy_variance = _safe_variance(rms_energy)

    pitch_track = librosa.yin(
        y,
        fmin=75,
        fmax=300,
        sr=sr,
        fill_na=np.nan,
    )
    pitch_track = pitch_track[np.isfinite(pitch_track) & (pitch_track > 0)]

    pitch_mean = _safe_mean(pitch_track)
    pitch_variance = _safe_variance(pitch_track)

    pitch_std = float(np.sqrt(pitch_variance))
    pitch_norm = pitch_std / max(pitch_mean, 1.0)
    monotony_score = _clamp(10.0 - pitch_norm * 12.0)

    pause_series = np.asarray(pause_durations, dtype=np.float32)
    pause_irregularity = _coefficient_of_variation(pause_series)
    energy_irregularity = _coefficient_of_variation(rms_energy)

    return {
        "duration_seconds": duration_seconds,
        "avg_energy": avg_energy,
        "energy_variance": energy_variance,
        "pause_irregularity": pause_irregularity,
        "energy_irregularity": energy_irregularity,
        "pauses": {
            "average_duration": average_pause_duration,
            "long_pause_count": long_pause_count,
            "pause_frequency": pause_frequency,
            "silence_ratio": silence_ratio,
        },
        "pitch": {
            "mean": pitch_mean,
            "variance": pitch_variance,
            "monotony_score": monotony_score,
        },
    }


def build_voice_metrics(
    raw_features: dict[str, Any],
    transcript: Any = None,
    duration_seconds: float | None = None,
) -> VoiceMetrics:
    pauses: dict[str, Any] = dict(raw_features.get("pauses", {}))
    pitch: dict[str, Any] = dict(raw_features.get("pitch", {}))

    effective_duration = float(
        duration_seconds if duration_seconds is not None else raw_features.get("duration_seconds", 0.0)
    )
    if effective_duration <= 0:
        effective_duration = 1.0

    transcript_text = ""
    if isinstance(transcript, list):
        transcript_text = " ".join(
            str(item.get("sentence", "")).strip()
            for item in transcript
            if isinstance(item, dict)
        ).strip()
    elif transcript is not None:
        transcript_text = str(transcript).strip()

    word_count = _safe_word_count(transcript_text)
    speech_rate = float(word_count / effective_duration)

    average_pause_duration = float(pauses.get("average_duration", 0.0))
    long_pause_count = int(pauses.get("long_pause_count", 0))
    pause_frequency = float(pauses.get("pause_frequency", 0.0))
    silence_ratio = float(pauses.get("silence_ratio", 0.0))

    pitch_mean = float(pitch.get("mean", 0.0))
    pitch_variance = float(pitch.get("variance", 0.0))
    monotony_score = float(pitch.get("monotony_score", 0.0))

    pause_pressure = (
        min(4.0, average_pause_duration * 2.0)
        + min(2.0, long_pause_count * 0.45)
        + min(2.5, silence_ratio * 4.0)
        + min(1.5, max(0.0, pause_frequency - 0.25) * 2.0)
    )

    speech_rate_distance = abs(speech_rate - IDEAL_SPEECH_RATE)
    speech_rate_pressure = min(
        2.5,
        (speech_rate_distance / IDEAL_SPEECH_RATE_TOLERANCE) * 1.8,
    )

    pitch_instability = 0.0
    if pitch_mean > 0:
        pitch_instability = min(2.5, (math.sqrt(pitch_variance) / pitch_mean) * 6.0)

    energy_irregularity = float(raw_features.get("energy_irregularity", 0.0))
    energy_pressure = min(2.0, energy_irregularity * 2.5)

    nervousness = _clamp(
        1.5
        + pause_pressure * 0.75
        + speech_rate_pressure * 0.7
        + pitch_instability * 0.6
        + energy_pressure * 0.4,
    )

    pacing_bonus = 0.0
    if 1.0 <= speech_rate <= 2.4:
        pacing_bonus = 1.0
    elif 0.8 <= speech_rate <= 2.8:
        pacing_bonus = 0.4

    confidence = _clamp(
        8.5
        - pause_pressure * 0.9
        - nervousness * 0.45
        + pacing_bonus
        + min(0.8, raw_features.get("avg_energy", 0.0) * 8.0),
    )

    return {
        "confidence": round(confidence, 2),
        "speech_rate": round(speech_rate, 2),
        "nervousness": round(nervousness, 2),
        "pauses": {
            "average_duration": round(average_pause_duration, 3),
            "long_pause_count": long_pause_count,
            "pause_frequency": round(pause_frequency, 3),
            "silence_ratio": round(silence_ratio, 3),
        },
        "pitch": {
            "mean": round(pitch_mean, 3),
            "variance": round(pitch_variance, 3),
            "monotony_score": round(monotony_score, 2),
        },
    }


def analyze_voice_metrics(
    audio_path: str,
    transcript: Any = None,
    duration_seconds: float | None = None,
) -> VoiceMetrics:
    raw_features = extract_voice_features(audio_path)
    return build_voice_metrics(
        raw_features=raw_features,
        transcript=transcript,
        duration_seconds=duration_seconds,
    )
