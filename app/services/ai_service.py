from __future__ import annotations

from typing import Any

from app.models.enums import TrainingMode

# from openai import OpenAI
# import os
# import json
from typing import Any

# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


SIMULATED_AI_PROMPT = """You are an expert interview evaluation engine.

You MUST follow these rules:
- Be strict and consistent in scoring
- Evaluate like a senior FAANG interviewer
- Do NOT be lenient or motivational
- Focus on real performance signals
- Return ONLY valid JSON (no markdown, no explanation)

Analyze the following interview answer:

Question:
{question}

Answer:
{transcript}

Return structured JSON with:

overall_score (0-10)

content:
- relevance (0-10)
- clarity (0-10)
- structure_star (0-10)
- specificity (0-10)

communication:
- conciseness (0-10)
- filler_word_count 
- pace (fast/normal/slow)
- confidence (0-10)

behavioral:
- ownership (0-10)
- initiative (0-10)
- impact (0-10)

flags:
- over_explaining
- rambling
- low_quantified_results
- blaming_language

primary_training_mode:
(delivery_training | structure_training | behavioral_training)

short_feedback:
Write 2–3 sentences only summarizing the candidate's main performance issue and strongest area.
"""


# def mock_ai_analysis(transcript: str, question: str) -> dict[str, Any]:
#     prompt = SIMULATED_AI_PROMPT.format(question=question, transcript=transcript)

#     response = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[
#             {
#                 "role": "system",
#                 "content": (
#                     "You are a strict interview scoring engine. "
#                     "Return ONLY valid JSON. No extra text."
#                 ),
#             },
#             {"role": "user", "content": prompt},
#         ],
#         response_format={"type": "json_object"},
#     )

#     result = json.loads(response.choices[0].message.content)

#     def safe(path, default=0):
#         try:
#             val = result
#             for p in path:
#                 val = val[p]
#             return val
#         except:
#             return default

#     return {
#         "overall_score": safe(["overall_score"]),
#         "content": {
#             "relevance": safe(["content", "relevance"]),
#             "clarity": safe(["content", "clarity"]),
#             "structure_star": safe(["content", "structure_star"]),
#             "specificity": safe(["content", "specificity"]),
#         },
#         "communication": {
#             "conciseness": safe(["communication", "conciseness"]),
#             "filler_word_count": safe(["communication", "filler_word_count"]),
#             "pace": safe(["communication", "pace"], "normal"),
#             "confidence": safe(["communication", "confidence"]),
#         },
#         "behavioral": {
#             "ownership": safe(["behavioral", "ownership"]),
#             "initiative": safe(["behavioral", "initiative"]),
#             "impact": safe(["behavioral", "impact"]),
#         },
#         "flags": result.get("flags", []),
#         "primary_training_mode": result.get(
#             "primary_training_mode", "structure_training"
#         ),
#         # 🔥 NEW: human-readable summary
#         "short_feedback": result.get(
#             "short_feedback",
#             "Performance shows mixed structure and clarity; improvement needed in answer organization and specificity.",
#         ),
#         "simulated_prompt": SIMULATED_AI_PROMPT,
#     }


FILLER_WORDS = ["um", "uh", "like", "you know", "basically", "actually"]


def mock_transcript(audio_input: str | None) -> str:
    if not audio_input:
        return "This is a simulated transcript of user answer. I handled the task with some detail and reflection."

    text = audio_input.lower()
    if "delivery" in text:
        return "Um, you know, I basically kept going and maybe over explained the answer because I wanted to be clear."
    if "structure" in text:
        return "I started with some background, then jumped around between points and never gave a clear sequence or direct outcome."
    if "behavior" in text or "ownership" in text:
        return "The team had issues, but I took ownership, decided what to do, and focused on the impact I created."
    return "This is a simulated transcript of user answer. I handled the task with some detail and reflection."


def _count_filler_words(text: str) -> int:
    lowered = text.lower()
    return sum(lowered.count(word) for word in FILLER_WORDS)


def _contains_any(text: str, phrases: list[str]) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def mock_ai_analysis(transcript: str, question: str) -> dict[str, Any]:
    word_count = len(transcript.split())
    filler_word_count = _count_filler_words(transcript)
    over_explaining = word_count > 110 or filler_word_count > 4
    rambling = word_count > 90 and not _contains_any(transcript, ["situation", "task", "action", "result"])
    low_quantified_results = not _contains_any(transcript, ["%", "percent", "results", "metric", "by", "reduced", "increased"])
    blaming_language = _contains_any(transcript, ["they made me", "they were wrong", "the team failed", "management"])

    structure_star = 8 if _contains_any(transcript, ["situation", "task", "action", "result"]) else 5
    if rambling:
        structure_star = max(2, structure_star - 2)

    confidence = 8
    if _contains_any(transcript, ["not sure", "maybe", "i think", "sort of"]):
        confidence = 5
    if over_explaining:
        confidence = min(confidence, 6)

    ownership = 8 if _contains_any(transcript, ["i owned", "i led", "i decided", "i took ownership", "i handled"]) else 5
    initiative = 8 if _contains_any(transcript, ["i started", "i proposed", "i initiated", "i took action"]) else 5
    impact = 8 if _contains_any(transcript, ["results", "impact", "improved", "reduced", "increased"]) else 5

    delivery_issue = over_explaining or filler_word_count >= 3 or confidence < 6
    structure_issue = structure_star < 6 or rambling
    behavioral_issue = ownership < 6 or initiative < 6 or impact < 6 or blaming_language

    if delivery_issue:
        primary_training_mode = TrainingMode.delivery_training.value
    elif structure_issue:
        primary_training_mode = TrainingMode.structure_training.value
    else:
        primary_training_mode = TrainingMode.behavioral_training.value if behavioral_issue else TrainingMode.structure_training.value

    relevance = 8 if question.lower().split()[0] in transcript.lower() else 6
    clarity = max(3, 10 - (filler_word_count // 2) - (2 if rambling else 0))
    specificity = 8 if _contains_any(transcript, ["for example", "specifically", "measured", "metric"]) else 5
    conciseness = max(2, 10 - (word_count // 25) - filler_word_count)
    overall_score = round((relevance + clarity + structure_star + specificity + conciseness + confidence + ownership + initiative + impact) / 9, 1)

    flags = []
    if over_explaining:
        flags.append("over_explaining")
    if rambling:
        flags.append("rambling")
    if low_quantified_results:
        flags.append("low_quantified_results")
    if blaming_language:
        flags.append("blaming_language")
    if filler_word_count > 0:
        flags.append("filler_words")

    return {
        "overall_score": overall_score,
        "content": {
            "relevance": relevance,
            "clarity": clarity,
            "structure_star": structure_star,
            "specificity": specificity,
        },
        "communication": {
            "conciseness": conciseness,
            "filler_word_count": filler_word_count,
            "pace": "fast" if word_count > 100 or filler_word_count >= 4 else "normal" if word_count > 45 else "slow",
            "confidence": confidence,
        },
        "behavioral": {
            "ownership": ownership,
            "initiative": initiative,
            "impact": impact,
        },
        "flags": flags,
        "primary_training_mode": primary_training_mode,
        "simulated_prompt": SIMULATED_AI_PROMPT,
    }


def select_training_mode(analysis: dict[str, Any]) -> list:
    flags = set(analysis.get("flags", []))
    content = analysis.get("content", {})
    communication = analysis.get("communication", {})
    behavioral = analysis.get("behavioral", {})

    modes: list[TrainingMode] = []

    if (
        {"over_explaining", "rambling"}.intersection(flags)
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
        else [analysis.get("primary_training_mode", TrainingMode.structure_training.value)]
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


