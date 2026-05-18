from __future__ import annotations

from typing import Any

from app.models.enums import TrainingMode


import os



from typing import Any
import re

from app.services.behavioral_analysis import analyze_behavioral_answer
from app.services.behavioral_analysis_fallback import analyze_behavioral_answer_fallback

# from __future__ import annotations

# import json
# import os
# from typing import Any

# from groq import Groq


# client = Groq(
#     api_key=os.getenv("GROQ_API_KEY")
# )

# MODEL = "llama-3.3-70b-versatile"


# SIMULATED_AI_PROMPT = """
# You are an expert behavioral interview evaluator.

# STRICT RULES:
# - Score like a senior FAANG interviewer
# - Be strict, objective, and consistent
# - Do NOT be motivational
# - Output ONLY valid JSON

# Question:
# {question}

# Answer:
# {transcript}

# Return JSON EXACTLY in this structure:

# {
#   "overall_score": float,
#   "content": {
#     "relevance": int,
#     "clarity": int,
#     "structure_star": int,
#     "specificity": int
#   },
#   "behavioral": {
#     "ownership": int,
#     "initiative": int,
#     "impact": int
#   },
#   "flags": [],
#   "sentence_feedback": [],
#   "behavioral_questions": [],
#   "star_example": {},
#   "primary_training_mode": "",
#   "short_feedback": ""
# }
# """


# BEHAVIORAL_PROMPT = """
# You are an expert behavioral interview evaluator.

# STRICT RULES:
# - Focus only on ownership, initiative, impact
# - Output ONLY valid JSON

# Question:
# {question}

# Answer:
# {transcript}

# Return EXACTLY:

# {
#   "overall_Behevioral_score": float,
#   "behavioral": {
#     "ownership": int,
#     "initiative": int,
#     "impact": int
#   },
#   "flags": [],
#   "short_feedback": "",
#   "pass": bool
# }
# """


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
#     return json.loads(content)


# def mock_ai_analysis(transcript: Any, question: str) -> dict[str, Any]:
#     prompt = SIMULATED_AI_PROMPT.format(
#         question=question,
#         transcript=str(transcript)
#     )

#     return _ask_groq(prompt)


# def mock_ai_beveviral_analysis(
#     transcript: Any,
#     question: str
# ) -> dict[str, Any]:

#     prompt = BEHAVIORAL_PROMPT.format(
#         question=question,
#         transcript=str(transcript)
#     )

#     return _ask_groq(prompt)


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
    {

    "overall_Behevioral_score": float (0-10),


  "behavioral": {
    "ownership": int (0-10),
    "initiative": int (0-10),
    "impact": int (0-10)
  },

    "flags": [
    "blaming_language"
  ],

  "short_feedback": "2-3 sentences max. Direct and critical."

   pass: true if ownership >=6, initiative >=6, impact >=6 and no blaming_language flag. Otherwise false.
}
 """




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
    # word_count = len(text.split())
    # filler_word_count = _count_filler_words(text)

    result = analyze_behavioral_answer_fallback(
        transcript=transcript,
        question=question,
    )

    # # --- STRUCTURE ---
    # has_star = _contains_any(text, ["situation", "task", "action", "result"])
    # structure_star = 7 if has_star else 4

    # rambling = word_count > 100 and not has_star
    # if rambling:
    #     structure_star -= 2

    # structure_star = max(2, min(10, structure_star))

    # # --- OWNERSHIP ---
    # ownership = 7
    # if "we" in text and "i" not in text:
    #     ownership -= 2
    # if _contains_any(text, STRONG_OWNERSHIP_PHRASES):
    #     ownership += 1

    # ownership = max(2, min(10, ownership))

    # # --- INITIATIVE ---
    # initiative = 6
    # if _contains_any(text, INITIATIVE_PHRASES):
    #     initiative += 2

    # # --- IMPACT ---
    # has_metrics = bool(re.search(r"\d", text))
    # impact = 6 + (2 if has_metrics else -2)
    # impact = max(2, min(10, impact))

    # # --- CONTENT ---
    # clarity = max(3, 10 - (filler_word_count // 2) - (2 if rambling else 0))
    # relevance = 7 if question.lower().split()[0] in text else 6
    # specificity = 7 if _contains_any(text, ["specifically", "for example"]) else 5

    # # --- FLAGS ---
    # flags = []
    # if rambling:
    #     flags.append("rambling")
    # if not has_metrics:
    #     flags.append("no_measurable_impact")
    # if specificity < 6:
    #     flags.append("low_specificity")
    # if _contains_any(text, ["they made me", "the team failed"]):
    #     flags.append("blaming_language")

    # # --- SENTENCE FEEDBACK ---
    # sentence_feedback = []

    # for sentence_row in transcript_sentences:
    #     idx = sentence_row["idx"]
    #     sentence_text = sentence_row["sentence"]
    #     is_weak, issue, issue_type = _is_weak_sentence(sentence_text)
    #     if is_weak:
    #         sentence_feedback.append({
    #             "idx": idx,
    #             "sentence_index": idx,
    #             "sentence": sentence_text,
    #             "indexed_sentence": f"[{idx}] {sentence_text}",
    #             "issue": issue,
    #             "improvement_type": issue_type,
    #             "improved_example": _generate_improvement(sentence_text, issue_type)
    #         })

    #     if len(sentence_feedback) >= 5:
    #         break

    # # --- TRAINING MODE ---
    # if structure_star < 6:
    #     primary_training_mode = "structure_training"
    # if ownership < 6 or impact < 6:
    #     primary_training_mode = "behavioral_training"
    # else:
    #     primary_training_mode = "structure_training"

    # # --- BEHAVIORAL QUESTIONS ---
    # behavioral_questions = [
    #     {
    #         "question": "What exactly did YOU do?",
    #         "target_improvement": "ownership",
    #         "strong_answer_example": "I led the implementation and made key decisions."
    #     },
    #     {
    #         "question": "What measurable result did you achieve?",
    #         "target_improvement": "impact",
    #         "strong_answer_example": "This reduced latency by 35%."
    #     }
    # ]

    # # --- STAR EXAMPLE ---
    # star_example = {
    #     "s": "During a project with performance issues.",
    #     "t": "I was responsible for improving performance.",
    #     "a": "I optimized database queries.",
    #     "r": "This improved response time by 40%."
    # }

    # # --- SCORE ---
    # overall_score = round(
    #     (relevance + clarity + structure_star + specificity + ownership + initiative + impact) / 7,
    #     1
    # )

    return {
        "overall_score": result['overall_score'],
        "transcript": transcript_text,
        "transcript_sentences": transcript_sentences,
        "content": {
            "relevance": result['scores']['relevance'],
            "clarity": result['scores']['clarity'],
            "structure_star": result['scores']['structure'],
            "specificity": result['scores']['specificity'],
        },
        "behavioral": {
            "ownership": result['scores']['ownership'],
            "initiative": result['scores']['initiative'],
            "impact": result['scores']['impact'],
        },
        "flags": result['flags'],
        "sentence_feedback": result['sentence_feedback'],
        "behavioral_questions": result['followup_questions'],
        "star_example": result['star_example'],
        "primary_training_mode": result['primary_training_mode'],
        "short_feedback": result['feedback'],
    }




def mock_ai_beveviral_analysis(transcript: Any, question: str) -> dict[str, Any]:
    transcript_sentences = _normalize_transcript_sentences(transcript)
    transcript_text = " ".join(item["sentence"] for item in transcript_sentences)
    text = transcript_text.lower()

    result = analyze_behavioral_answer(text, question )

    # has_metrics = bool(re.search(r"\d", text))
    # has_blaming = _contains_any(text, ["they made me", "the team failed", "my manager blocked", "it was their fault"])

    # ownership = 6
    # if _contains_any(text, WEAK_PATTERNS):
    #     ownership -= 2
    # if _contains_any(text, STRONG_OWNERSHIP_PHRASES):
    #     ownership += 2
    # if " we " in f" {text} " and " i " not in f" {text} ":
    #     ownership -= 2
    # ownership = max(0, min(10, ownership))

    # initiative = 5
    # if _contains_any(text, INITIATIVE_PHRASES):
    #     initiative += 2
    # if _contains_any(text, ["i took initiative", "i drove", "i volunteered", "i proactively"]):
    #     initiative += 1
    # initiative = max(0, min(10, initiative))

    # impact = 5
    # if has_metrics:
    #     impact += 3
    # else:
    #     impact -= 1
    # if _contains_any(text, IMPACT_KEYWORDS):
    #     impact += 1
    # impact = max(0, min(10, impact))

    # flags: list[str] = []
    # if has_blaming:
    #     flags.append("blaming_language")

    # passed = ownership >= 6 and initiative >= 6 and impact >= 6 and "blaming_language" not in flags
    # overall_behavioral_score = round((ownership + initiative + impact) / 3, 1)

    # if not passed:
    #     short_feedback = (
    #         "Behavioral signal is not strong enough yet. Increase ownership language, show clearer initiative, "
    #         "and include measurable impact from your actions."
    #     )
    # else:
    #     short_feedback = (
    #         "Behavioral signal is acceptable. Ownership, initiative, and impact are visible and mostly concrete."
    #     )

    return {
        "overall_Behevioral_score": result['overall_score'],
        "overall_score": result['overall_score'],
        "behavioral": {
            "ownership": result['ownership'],
            "initiative": result['initiative'],
            "impact": result['impact'],
        },
        "flags": result['flags'],
        "short_feedback": result['feedback'],
        "pass": result['passed'],
        "question": question,
        "transcript": transcript_text,
        "transcript_sentences": transcript_sentences,
        "simulated_prompt": simulated_behavioral_prompt,
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


