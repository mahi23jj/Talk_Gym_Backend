from typing import Any

from app.models.enums import TrainingMode


def select_training_mode(analysis: dict[str, Any]) -> list:
    flags = set(analysis.get("flags", []))
    content = analysis.get("content", {})
    communication = analysis.get("communication", {})
    behavioral = analysis.get("behavioral", {})

    modes: list[TrainingMode] = []

    if (
        {
            "over_explaining",
            "rambling",
        }.intersection(flags)
        or communication.get("pace") == "fast"
        or communication.get("confidence", 10) < 6
    ):
        modes.append(TrainingMode.delivery_training)

    if communication.get("filler_word_count", 0) > 3:
        modes.append(TrainingMode.delivery_training)

    if content.get("structure_star", 10) < 6 or "rambling" in flags:
        modes.append(TrainingMode.structure_training)

    if (
        behavioral.get("ownership", 10) < 6
        or behavioral.get("initiative", 10) < 6
        or behavioral.get("impact", 10) < 6
        or "blaming_language" in flags
    ):
        modes.append(TrainingMode.behavioral_training)

    return (
        modes
        if modes
        else [
            analysis.get("primary_training_mode", TrainingMode.structure_training.value)
        ]
    )


def build_training_instructions(training_mode: str) -> list[str]:
    if training_mode == TrainingMode.delivery_training.value:
        return [
            "Answer in 60 seconds.",
            "Speak with a steady pace and remove filler words.",
            "Sound confident and keep the answer concise.",
        ]
    if training_mode == TrainingMode.structure_training.value:
        return [
            "Use STAR format: Situation, Task, Action, Result.",
            "Answer in a clear linear flow.",
            "Make the Result measurable when possible.",
        ]
    return [
        "Focus on ownership, initiative, and impact.",
        "Remove blame and speak from your own actions.",
        "Emphasize what you specifically contributed.",
    ]


def build_training_followups(training_mode: str) -> list[str]:
    if training_mode == TrainingMode.delivery_training.value:
        return [
            "What specific filler words did you notice in your answer?",
            "Did you feel rushed or confident in your delivery?",
            "How did the pacing of your answer feel to you?",
        ]
    if training_mode == TrainingMode.structure_training.value:
        return [
            "Can you identify the Situation, Task, Action, and Result in your answer?",
            "Was there any part of your answer that felt unclear or out of order?",
            "How could you make the Result more measurable or specific?",
        ]
    return [
        "Where did you take ownership in your answer?",
        "What initiative did you show in the situation you described?",
        "How did you demonstrate impact in your answer?",
    ]
