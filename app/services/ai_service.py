from __future__ import annotations

from typing import Any

from app.models.enums import TrainingMode

from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


SIMULATED_AI_PROMPT = """You are an expert behavioral interview evaluator.

STRICT RULES:
- Score like a senior FAANG interviewer
- Be strict, objective, and consistent
- Do NOT be motivational or polite
- Focus only on performance signals
- Output ONLY valid JSON (no markdown, no explanation)

Analyze the interview response below.

Question:
{question}

Answer (indexed sentence list source):
{transcript}

Return JSON with this EXACT structure:

{
  "overall_score": float (0-10),

  "content": {
    "relevance": int (0-10),
    "clarity": int (0-10),
    "structure_star": int (0-10),
    "specificity": int (0-10)
  },

  "behavioral": {
    "ownership": int (0-10),
    "initiative": int (0-10),
    "impact": int (0-10)
  },

  "flags": [
    "rambling",
    "blaming_language",
    "low_specificity",
    "no_measurable_impact"
  ],

  "sentence_feedback": [
    {
    "idx": int,
    "sentence_index": int,
    "sentence": "...",
    "indexed_sentence": "[idx] sentence",
      "issue": "...",
      "improvement_type": "ownership | impact | specificity | clarity",
      "improved_example": "..."
    }
  ],

  "behavioral_questions": [
    {
      "question": "...",
      "target_improvement": "...",
      "strong_answer_example": "..."
    }
  ],

  "star_example": {
    "s": "...",
    "t": "...",
    "a": "...",
    "r": "..."
  },

  "primary_training_mode": "structure_training" | "behavioral_training",

  "short_feedback": "2-3 sentences max. Direct and critical."
}

Each sentence_feedback item MUST preserve the exact source sentence index from input.
Do not reorder indexes and do not invent new indexes.
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


from typing import Any
import re

FILLER_WORDS = ["um", "uh", "like", "you know", "sort of", "kind of"]

WEAK_PATTERNS = ["helped", "worked on", "involved in", "did some", "we "]

STRONG_OWNERSHIP_PHRASES = [
    "i led", "i owned", "i decided", "i implemented", "i designed"
]

INITIATIVE_PHRASES = [
    "i proposed", "i initiated", "i started", "i identified"
]

IMPACT_KEYWORDS = [
    "%", "percent", "reduced", "increased", "improved", "saved"
]


def _count_filler_words(text: str) -> int:
    lowered = text.lower()
    return sum(lowered.count(word) for word in FILLER_WORDS)


def _contains_any(text: str, phrases: list[str]) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]


def _normalize_transcript_sentences(transcript: Any) -> list[dict[str, Any]]:
    if isinstance(transcript, list):
        normalized: list[dict[str, Any]] = []
        for fallback_idx, item in enumerate(transcript):
            if not isinstance(item, dict):
                continue

            sentence = str(item.get("sentence", "")).strip()
            if not sentence:
                continue

            raw_idx = item.get("idx", item.get("index", fallback_idx))
            try:
                idx = int(raw_idx)
            except (TypeError, ValueError):
                idx = fallback_idx

            normalized.append({"idx": idx, "sentence": sentence})
        return normalized

    transcript_text = str(transcript or "")
    sentences = _split_sentences(transcript_text)
    return [{"idx": idx, "sentence": sentence} for idx, sentence in enumerate(sentences)]


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


def mock_ai_analysis(transcript: Any, question: str) -> dict[str, Any]:
    transcript_sentences = _normalize_transcript_sentences(transcript)
    transcript_text = " ".join(item["sentence"] for item in transcript_sentences)
    text = transcript_text.lower()
    word_count = len(text.split())
    filler_word_count = _count_filler_words(text)

    # --- STRUCTURE ---
    has_star = _contains_any(text, ["situation", "task", "action", "result"])
    structure_star = 7 if has_star else 4

    rambling = word_count > 100 and not has_star
    if rambling:
        structure_star -= 2

    structure_star = max(2, min(10, structure_star))

    # --- OWNERSHIP ---
    ownership = 7
    if "we" in text and "i" not in text:
        ownership -= 2
    if _contains_any(text, STRONG_OWNERSHIP_PHRASES):
        ownership += 1

    ownership = max(2, min(10, ownership))

    # --- INITIATIVE ---
    initiative = 6
    if _contains_any(text, INITIATIVE_PHRASES):
        initiative += 2

    # --- IMPACT ---
    has_metrics = bool(re.search(r"\d", text))
    impact = 6 + (2 if has_metrics else -2)
    impact = max(2, min(10, impact))

    # --- CONTENT ---
    clarity = max(3, 10 - (filler_word_count // 2) - (2 if rambling else 0))
    relevance = 7 if question.lower().split()[0] in text else 6
    specificity = 7 if _contains_any(text, ["specifically", "for example"]) else 5

    # --- FLAGS ---
    flags = []
    if rambling:
        flags.append("rambling")
    if not has_metrics:
        flags.append("no_measurable_impact")
    if specificity < 6:
        flags.append("low_specificity")
    if _contains_any(text, ["they made me", "the team failed"]):
        flags.append("blaming_language")

    # --- SENTENCE FEEDBACK ---
    sentence_feedback = []

    for sentence_row in transcript_sentences:
        idx = sentence_row["idx"]
        sentence_text = sentence_row["sentence"]
        is_weak, issue, issue_type = _is_weak_sentence(sentence_text)
        if is_weak:
            sentence_feedback.append({
                "idx": idx,
                "sentence_index": idx,
                "sentence": sentence_text,
                "indexed_sentence": f"[{idx}] {sentence_text}",
                "issue": issue,
                "improvement_type": issue_type,
                "improved_example": _generate_improvement(sentence_text, issue_type)
            })

        if len(sentence_feedback) >= 5:
            break

    # --- TRAINING MODE ---
    if structure_star < 6:
        primary_training_mode = "structure_training"
    if ownership < 6 or impact < 6:
        primary_training_mode = "behavioral_training"
    else:
        primary_training_mode = "behavioral_training"

    # --- BEHAVIORAL QUESTIONS ---
    behavioral_questions = [
        {
            "question": "What exactly did YOU do?",
            "target_improvement": "ownership",
            "strong_answer_example": "I led the implementation and made key decisions."
        },
        {
            "question": "What measurable result did you achieve?",
            "target_improvement": "impact",
            "strong_answer_example": "This reduced latency by 35%."
        }
    ]

    # --- STAR EXAMPLE ---
    star_example = {
        "s": "During a project with performance issues.",
        "t": "I was responsible for improving performance.",
        "a": "I optimized database queries.",
        "r": "This improved response time by 40%."
    }

    # --- SCORE ---
    overall_score = round(
        (relevance + clarity + structure_star + specificity + ownership + initiative + impact) / 7,
        1
    )

    return {
        "overall_score": overall_score,
        "transcript": transcript_text,
        "transcript_sentences": transcript_sentences,
        "content": {
            "relevance": relevance,
            "clarity": clarity,
            "structure_star": structure_star,
            "specificity": specificity,
        },
        "behavioral": {
            "ownership": ownership,
            "initiative": initiative,
            "impact": impact,
        },
        "flags": flags,
        "sentence_feedback": sentence_feedback,
        "behavioral_questions": behavioral_questions,
        "star_example": star_example,
        "primary_training_mode": primary_training_mode,
        "short_feedback": "Answer lacks strong ownership and measurable impact. Structure is partially clear but needs more specific actions and results.",
        "simulated_prompt": SIMULATED_AI_PROMPT,
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
        else [analysis.get("primary_training_mode", TrainingMode.structure_training.value)]
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


