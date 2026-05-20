from __future__ import annotations


import asyncio
from asyncio.log import logger
import json
from typing import Any

from groq import Groq

from app.models.enums import TrainingMode


import os

# Default model name for Groq or other LLM client. Can be overridden via env var GROQ_MODEL
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


import re

from app.services.behavioral_analysis import analyze_behavioral_answer
from app.services.behavioral_analysis_fallback import analyze_behavioral_answer_fallback


import logging

logger = logging.getLogger(__name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


# def _ask_groq(prompt: str) -> dict[str, Any]:
#     response = client.chat.completions.create(
#         model=MODEL,
#         temperature=0.2,
#         response_format={"type": "json_object"},
#         messages=[
#             {
#                 "role": "system",
#                 "content": "Return only valid JSON."
#             },
#             {
#                 "role": "user",
#                 "content": prompt
#             }
#         ],
#     )

#     content = response.choices[0].message.content

#     print("GROQ RAW RESPONSE:", json.loads(content))
#     return json.loads(content)


# def run_ai_analysis(transcript: Any, question: str) -> dict[str, Any]:
#     """
#     Blocking function — always call via asyncio.to_thread().
#     Never raises; returns a fallback payload on any error.
#     """
#     sentences = _normalize_transcript_sentences(transcript)

#     prompt = SIMULATED_AI_PROMPT.format(question=question, transcript=sentences)
#     result = _ask_groq(prompt)

#         # Ensure the transcript fields are present (Groq won't return them)
#     result.setdefault("transcript", transcript)
#     result.setdefault("transcript_sentences", sentences)

#         # Coerce overall_score to float just in case Groq returns a string
#     result["overall_score"] = float(result.get("overall_score", 0.0))

#         # logger.info("Groq analysis complete. overall_score=%.2f", result["overall_score"])
#     return result


# async def ai_analysis_async(transcript: Any, question: str) -> dict[str, Any]:
#     """
#     Drop-in async replacement for mock_ai_analysis().
#     Offloads the blocking Groq HTTP call to a thread pool.
#     """
#     return await asyncio.to_thread(run_ai_analysis, transcript, question)


# # def mock_ai_beveviral_analysis(
# #     transcript: Any,
# #     question: str
# # ) -> dict[str, Any]:

# #     prompt = BEHAVIORAL_PROMPT.format(
# #         question=question,
# #         transcript=str(transcript)
# #     )

# #     return _ask_groq(prompt)

# def _split_sentences(text: str) -> list[str]:
#     return [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]


# def _normalize_transcript_sentences(transcript: Any) -> list[dict[str, Any]]:
#     if isinstance(transcript, list):
#         normalized: list[dict[str, Any]] = []
#         for fallback_idx, item in enumerate(transcript):
#             if not isinstance(item, dict):
#                 continue

#             sentence = str(item.get("sentence", "")).strip()
#             if not sentence:
#                 continue

#             raw_idx = item.get("idx", item.get("index", fallback_idx))
#             try:
#                 idx = int(raw_idx)
#             except (TypeError, ValueError):
#                 idx = fallback_idx

#             normalized.append({"idx": idx, "sentence": sentence})
#         return normalized

#     transcript_text = str(transcript or "")
#     sentences = _split_sentences(transcript_text)
#     return [{"idx": idx, "sentence": sentence} for idx, sentence in enumerate(sentences)]


# SIMULATED_AI_PROMPT = """You are an expert behavioral interview evaluator.

# STRICT RULES:
# - Score like a senior FAANG interviewer
# - Be strict, objective, and consistent
# - Do NOT be motivational or polite
# - Focus only on performance signals
# - Output ONLY valid JSON (no markdown, no explanation)

# Analyze the interview response below.

# Question:
# {question}

# Answer (indexed sentence list source):
# {transcript}

# Return JSON with this EXACT structure:

# {{
#   "overall_score": float (0-10),

#   "content": {{
#     "relevance": int (0-10),
#     "clarity": int (0-10),
#     "structure_star": int (0-10),
#     "specificity": int (0-10)
#   }},

#   "behavioral": {{
#     "ownership": int (0-10),
#     "initiative": int (0-10),
#     "impact": int (0-10)
#   }},

#   "flags": [
#     "rambling",
#     "blaming_language",
#     "low_specificity",
#     "no_measurable_impact"
#   ],

#   "sentence_feedback": [
#     {{
#     "idx": int,
#     "sentence_index": int,
#     "sentence": "...",
#     "indexed_sentence": "[idx] sentence",
#       "issue": "...",
#       "improvement_type": "ownership | impact | specificity | clarity",
#       "improved_example": "..."
#     }}
#   ],

#   "behavioral_questions": [
#     {{
#       "question": "...",
#       "target_improvement": "...",
#       "strong_answer_example": "..."
#     }}
#   ],

#   "star_example": {{
#     "s": "...",
#     "t": "...",
#     "a": "...",
#     "r": "..."
#   }},

#   "primary_training_mode": "structure_training" | "behavioral_training",

#   "short_feedback": "2-3 sentences max. Direct and critical."
# }}

# Each sentence_feedback item MUST preserve the exact source sentence index from input.
# Do not reorder indexes and do not invent new indexes.
# """


# def mock_ai_analysis(transcript: Any, question: str) -> dict[str, Any]:
#     transcript_sentences = _normalize_transcript_sentences(transcript)
#     transcript_text = " ".join(item["sentence"] for item in transcript_sentences)
#     text = transcript_text.lower()
#     # word_count = len(text.split())
#     # filler_word_count = _count_filler_words(text)

#     result = analyze_behavioral_answer_fallback(
#         transcript=transcript,
#         question=question,
#     )
#     # # --- STRUCTURE ---
#     return {
#         "overall_score": result['overall_score'],
#         "transcript": transcript_text,
#         "transcript_sentences": transcript_sentences,
#         "content": {
#             "relevance": result['scores']['relevance'],
#             "clarity": result['scores']['clarity'],
#             "structure_star": result['scores']['structure'],
#             "specificity": result['scores']['specificity'],
#         },
#         "behavioral": {
#             "ownership": result['scores']['ownership'],
#             "initiative": result['scores']['initiative'],
#             "impact": result['scores']['impact'],
#         },
#         "flags": result['flags'],
#         "sentence_feedback": result['sentence_feedback'],
#         "behavioral_questions": result['followup_questions'],
#         "star_example": result['star_example'],
#         "primary_training_mode": result['primary_training_mode'],
#         "short_feedback": result['feedback'],
#     }


# ---------------------------
# Transcript normalization
# ---------------------------


def _split_sentences(text: str) -> list[str]:
    """
    Split noisy ASR transcript into sentence-like chunks.
    Handles commas too.
    """
    return [s.strip() for s in re.split(r"[.!?,;]+", text) if s.strip()]


def _normalize_transcript_sentences(transcript: Any) -> list[dict[str, Any]]:

    if isinstance(transcript, list):
        normalized = []

        for fallback_idx, item in enumerate(transcript):
            if not isinstance(item, dict):
                continue

            sentence = str(item.get("sentence", "")).strip()

            if not sentence:
                continue

            raw_idx = item.get("idx", item.get("index", fallback_idx))

            try:
                idx = int(raw_idx)
            except Exception:
                idx = fallback_idx

            normalized.append({"idx": idx, "sentence": sentence})

        return normalized

    transcript_text = str(transcript or "")

    split = _split_sentences(transcript_text)

    return [{"idx": i, "sentence": s} for i, s in enumerate(split)]


def _format_for_prompt(transcript_sentences: list[dict[str, Any]]) -> str:
    return "\n".join(f"[{x['idx']}] {x['sentence']}" for x in transcript_sentences)


# ---------------------------
# Groq
# ---------------------------


def _ask_groq(prompt: str) -> dict[str, Any]:

    response = client.chat.completions.create(
        model=MODEL,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Return only valid JSON."},
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content

    parsed = json.loads(content)

    logger.info("Groq analysis OK")

    return parsed


# ---------------------------
# Main hybrid analyzer
# ---------------------------


def run_ai_analysis(transcript: Any, question: str) -> dict[str, Any]:

    transcript_sentences = _normalize_transcript_sentences(transcript)

    transcript_text = " ".join(x["sentence"] for x in transcript_sentences)

    fallback = analyze_behavioral_answer_fallback(
        transcript=transcript, question=question
    )

    formatted = _format_for_prompt(transcript_sentences)

    return {
            "overall_score": fallback["overall_score"],
            "transcript": transcript_text,
            "transcript_sentences": formatted ,
            "content": {
                "relevance": fallback["scores"]["relevance"],
                "clarity": fallback["scores"]["clarity"],
                "structure_star": fallback["scores"]["structure"],
                "specificity": fallback["scores"]["specificity"],
            },
            "behavioral": {
                "ownership": fallback["scores"]["ownership"],
                "initiative": fallback["scores"]["initiative"],
                "impact": fallback["scores"]["impact"],
            },
            "flags":("flags", fallback["flags"]),
            "sentence_feedback": ("sentence_feedback", fallback["sentence_feedback"]),
            "behavioral_questions": ("behavioral_questions", fallback["followup_questions"]),
            "star_example": ("star_example", fallback["star_example"]),
            "primary_training_mode": ("primary_training_mode", fallback["primary_training_mode"]),
            "short_feedback": ("short_feedback", fallback["feedback"]),
        }

    """  try:

        formatted = _format_for_prompt(transcript_sentences)

        prompt = SIMULATED_AI_PROMPT.format(question=question, transcript=formatted)

        ai = _ask_groq(prompt)

        return {
            "overall_score": float(fallback["overall_score"]),
            "transcript": transcript_text,
            "transcript_sentences": transcript_sentences,
            "content": {
                "relevance": fallback["scores"]["relevance"],
                "clarity": fallback["scores"]["clarity"],
                "structure_star": fallback["scores"]["structure"],
                "specificity": fallback["scores"]["specificity"],
            },
            "behavioral": {
                "ownership": fallback["scores"]["ownership"],
                "initiative": fallback["scores"]["initiative"],
                "impact": fallback["scores"]["impact"],
            },
            "flags": ai.get("flags", fallback["flags"]),
            "sentence_feedback": ai.get(
                "sentence_feedback", fallback["sentence_feedback"]
            ),
            "behavioral_questions": ai.get(
                "behavioral_questions", fallback["followup_questions"]
            ),
            "star_example": ai.get("star_example", fallback["star_example"]),
            "primary_training_mode": ai.get("primary_training_mode", fallback["primary_training_mode"]),
            "short_feedback": ai.get("short_feedback", fallback["feedback"]),
        }

    except Exception:

        logger.exception("Groq failed — fallback used")

        return {
            "overall_score": fallback["overall_score"],
            "transcript": transcript_text,
            "transcript_sentences": transcript_sentences,
            "content": {
                "relevance": fallback["scores"]["relevance"],
                "clarity": fallback["scores"]["clarity"],
                "structure_star": fallback["scores"]["structure"],
                "specificity": fallback["scores"]["specificity"],
            },
            "behavioral": {
                "ownership": fallback["scores"]["ownership"],
                "initiative": fallback["scores"]["initiative"],
                "impact": fallback["scores"]["impact"],
            },
            "flags": ai.get("flags", fallback["flags"]),
            "sentence_feedback": ai.get("sentence_feedback", fallback["sentence_feedback"]),
            "behavioral_questions": ai.get("behavioral_questions", fallback["followup_questions"]),
            "star_example": ai.get("star_example", fallback["star_example"]),
            "primary_training_mode": ai.get("primary_training_mode", fallback["primary_training_mode"]),
            "short_feedback": ai.get("short_feedback", fallback["feedback"]),
        }
 """

def mock_ai_analysis(transcript: Any, question: str) -> dict[str, Any]:
    return run_ai_analysis(transcript, question)


async def ai_analysis_async(transcript: Any, question: str):
    return await asyncio.to_thread(run_ai_analysis, transcript, question)


# ---------------------------
# Prompt
# ---------------------------

SIMULATED_AI_PROMPT = """
You are a senior behavioral interview evaluator.

STRICT RULES:

- Analyze each indexed sentence separately
- NEVER merge multiple sentences
- Preserve exact sentence text
- Preserve exact sentence indexes
- Generate realistic workplace examples
- NEVER use placeholders like:
  "Specific situation"
  "Task or challenge"
  "Action taken"
  "Result"
- on flag list for me a problems that you can identify in the answer, such as "rambling", "blaming_language", "low_specificity", "no_measurable_impact"
- For sentence feedback, be direct and critical. Focus on ownership, initiative, impact, clarity

STAR examples must be concrete and realistic.

Sentence feedback must reference exact source sentence.

Question:
{question}

Transcript:
{transcript}

Return ONLY valid JSON:

{{
  "sentence_feedback": [
    {{
      "idx": int,
      "sentence_index": int,
      "sentence": "...",
      "indexed_sentence": "[idx] exact sentence",
      "issue": "...",
      "improvement_type":
        "ownership|impact|specificity|clarity",
      "improved_example": "..."
    }}
  ],

  "behavioral_questions": [
    {{
      "question": "...",
      "target_improvement": "...",
      "strong_answer_example": "..."
    }}
  ],

  "star_example": {{
    "s": "...",
    "t": "...",
    "a": "...",
    "r": "..."
  }},

  "flags": [
    ],

  "primary_training_mode": "structure_training" | "behavioral_training",

  "short_feedback": "Direct coaching feedback"
}}
"""

simulated_behavioral_prompt = """You are an expert behavioral interview coach.
 
 STRICT RULES:
 
 
 - Focus ONLY on ownership, initiative, and impact feedback
 - Be direct, critical, and actionable

    Analyze the interview response below.
    Question:
    {question}
    Answer (indexed sentence list source):
    {transcript}
    Return JSON with this EXACT structure:
    {{

    "overall_Behevioral_score": float (0-10),


  "behavioral": {{
    "ownership": int (0-10),
    "initiative": int (0-10),
    "impact": int (0-10)
  }},

    "flags": [
    "blaming_language"
  ],

  "short_feedback": "2-3 sentences max. Direct and critical."

   pass: true if ownership >=6, initiative >=6, impact >=6 and no blaming_language flag. Otherwise false.
}}
 """


FILLER_WORDS = ["um", "uh", "like", "you know", "sort of", "kind of"]

WEAK_PATTERNS = ["helped", "worked on", "involved in", "did some", "we "]

STRONG_OWNERSHIP_PHRASES = [
    "i led",
    "i owned",
    "i decided",
    "i implemented",
    "i designed",
]

INITIATIVE_PHRASES = ["i proposed", "i initiated", "i started", "i identified"]

IMPACT_KEYWORDS = ["%", "percent", "reduced", "increased", "improved", "saved"]


def _count_filler_words(text: str) -> int:
    lowered = text.lower()
    return sum(lowered.count(word) for word in FILLER_WORDS)


def _contains_any(text: str, phrases: list[str]) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def _is_weak_sentence(sentence: str) -> tuple[bool, str, str]:
    s = sentence.lower()

    # Ownership issue
    if any(p in s for p in WEAK_PATTERNS):
        return True, "Weak ownership or vague contribution", "ownership"

    # Impact issue
    if ("improve" in s or "result" in s) and not re.search(r"\d", s):
        return True, "Lacks measurable impact", "impact"

    # Specificity issue
    if len(s.split()) < 6:
        return True, "Too vague or lacks detail", "specificity"

    return False, "", ""


def _generate_improvement(sentence: str, issue_type: str) -> str:
    if issue_type == "ownership":
        return "Rewrite using strong ownership: 'I led...', 'I implemented...', 'I designed...'"
    elif issue_type == "impact":
        return "Add measurable results: '...which improved performance by 30%'"
    elif issue_type == "specificity":
        return "Add specific details about what you did and how"
    else:
        return "Make the sentence clearer and more specific"


def mock_ai_beveviral_analysis(
    transcript: Any,
    question: str
) -> dict[str, Any]:

    transcript_sentences = _normalize_transcript_sentences(transcript)
    transcript_text = " ".join(
        item["sentence"] for item in transcript_sentences
    )

    result = analyze_behavioral_answer(
        transcript=transcript_sentences,
        question=question,
    )

    scores = result.get("scores", {})
    star = result.get("star_analysis", {})

    return {
        "overall_Behevioral_score": result.get("overall_score", 0),
        "overall_score": result.get("overall_score", 0),

        "behavioral": {
            "ownership": scores.get("ownership", 0),
            "initiative": scores.get("initiative", 0),
            "impact": scores.get("impact", 0),
        },

        "content": {
            "structure_star": scores.get("structure", 0),
            "star_sequence_score": star.get("sequence_score", 0),
            "phases_detected": star.get("phases_detected", []),
            "order_correct": star.get("order_correct", False),
        },

        "flags": result.get("flags", []),

        "short_feedback": result.get(
            "feedback",
            "Behavioral analysis completed."
        ),

        "pass": result.get("passed", False),

        "question": question,

        "transcript": transcript_text,
        "transcript_sentences": transcript_sentences,

        "rubric_version": result.get("rubric_version", "3.0"),
    }


def select_training_mode(analysis: dict[str, Any]) -> list:
    flags = set(analysis.get("flags", []))
    content = analysis.get("content", {})
    behavioral = analysis.get("behavioral", {})

    modes: list[TrainingMode] = []

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
