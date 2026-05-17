"""
Behavioral Interview Analysis — Deterministic Fallback Engine
============================================================
Used when AI analyzer quota is exhausted.
Designed to feel intelligent, not static — adaptive outputs,
question-aware coaching, prioritized feedback, dynamic STAR examples.

No LLM calls. All deterministic.
"""

from __future__ import annotations
import re
from typing import Any


# ---------------------------------------------------------------------------
# PHRASE LIBRARIES
# ---------------------------------------------------------------------------

FILLER_PATTERNS = [
    r"\b(um+|uh+)\b",
    r"\blike\b(?!\s+\w+ed|\s+a\s|\s+the\s)",  # "like" as filler, not comparison
    r"\byou know\b",
    r"\bsort of\b",
    r"\bkind of\b",
    r"\bi mean\b",
    r"\bbasically\b",
    r"\bliterally\b",
    r"\bhonestly\b",
    r"\bright\?\s",
    r"\bso yeah\b",
    r"\bdoes that make sense\b",
    r"\bif that makes sense\b",
]

WEAK_OWNERSHIP_PATTERNS = [
    r"\bwe (all|just|kind of|sort of|basically)\b",
    r"\b(helped|assisted|supported) (with|on|the)\b",
    r"\bwas involved in\b",
    r"\bdid some\b",
    r"\bworked on\b(?! (a|the|my|this|that) (system|feature|project|problem|solution))",
    r"\bpart of (a|the) team\b",
    r"\bwe were (told|asked|required)\b",
    r"\bjust followed\b",
    r"\bi guess\b",
    r"\bmaybe i\b",
    r"\bi think i\b",
    r"\bnot (really )?sure (why|how|who)\b",
]

STRONG_OWNERSHIP_PATTERNS = [
    r"\bi (decided|chose|initiated|drove|led|owned|took ownership)\b",
    r"\bi made the (decision|call|choice)\b",
    r"\bi (proposed|designed|built|created|implemented|architected)\b",
    r"\bi (stepped up|volunteered|raised|flagged|escalated)\b",
    r"\bi took (responsibility|the lead|initiative|charge)\b",
    r"\bmy (decision|idea|proposal|approach|solution)\b",
    r"\bi was responsible for\b",
    r"\bi (pushed|advocated|argued) for\b",
    r"\bi held myself\b",
    r"\bi (realized|noticed|identified|spotted) (the problem|an issue|a gap)\b",
]

BLAMING_PATTERNS = [
    r"\bthey (made|forced|told|caused|blocked|prevented)\b",
    r"\bit was (their|his|her|the team'?s?) fault\b",
    r"\bmy manager (blocked|refused|wouldn'?t|didn'?t allow)\b",
    r"\bwe had no choice\b",
    r"\bthe situation forced\b",
    r"\bno one (told|informed|warned) me\b",
    r"\bi wasn'?t (told|informed|given)\b",
    r"\bit wasn'?t (really )?my (fault|responsibility|job)\b",
    r"\bout of my (hands|control)\b",
]

INITIATIVE_PATTERNS = [
    r"\bi (proactively|independently|voluntarily)\b",
    r"\bwithout (being asked|being told|direction|prompting)\b",
    r"\bon my own (initiative|accord)\b",
    r"\bi (proposed|suggested|recommended) (a|the|this|an)\b",
    r"\bi (reached out|contacted|approached)\b",
    r"\bi didn'?t wait\b",
    r"\bi (started|began|kicked off|launched)\b",
    r"\bi (identified|spotted|noticed) .{0,30} (before|early|ahead)\b",
]

IMPACT_PATTERNS = [
    r"\b\d+\s*(%|percent)\b",
    r"\b\d+x\b",
    r"\b\d+\s*(hours?|days?|weeks?|months?)\s*(faster|saved|reduced|less)\b",
    r"\breduced (by|from)\b",
    r"\bincreased (by|from)\b",
    r"\bimproved (by|from)\b",
    r"\bsaved .{0,20}(time|hours?|money|\$|cost)\b",
    r"\bgrew (by|to|from)\b",
    r"\bdelivered (on time|early|ahead|under budget)\b",
    r"\bthe (result|outcome|impact) was\b",
    r"\bas a result\b",
    r"\bwhich (led to|resulted in|meant|allowed|enabled)\b",
]

# STAR phase detection by sentence
_STAR_PHASES = {
    "situation": [
        r"\b(at the time|back then|this was|we were|i was working)\b",
        r"\bthe (problem|challenge|situation|issue) was\b",
        r"\bwe (had|faced|were dealing with|were trying to)\b",
        r"\bour (team|company|product|system) (was|had|needed)\b",
        r"\bcontext\b",
    ],
    "task": [
        r"\bmy (role|job|responsibility|goal|objective|task) was\b",
        r"\bi (was responsible for|was asked to|needed to|had to)\b",
        r"\bthe (goal|objective|target|requirement) was\b",
    ],
    "action": [
        r"\bi (decided|chose|started|built|designed|implemented|wrote|created)\b",
        r"\bfirst[,\s] i\b",
        r"\bso i\b",
        r"\bmy approach was\b",
        r"\bi then\b",
        r"\bspecifically[,\s] i\b",
    ],
    "result": [
        r"\bas a result\b",
        r"\bthe (result|outcome|impact) (was|is)\b",
        r"\bin the end\b",
        r"\bultimately\b",
        r"\bwe (achieved|reached|hit|exceeded|delivered|shipped)\b",
        r"\bthis (led to|resulted in|meant|allowed|enabled)\b",
        r"\bafter (this|that|the change|implementing)\b",
    ],
}

# Question keyword → competency domain mapping
# Used to make coaching question-aware
_QUESTION_DOMAIN_HINTS = {
    "conflict":     ["conflict", "disagree", "difficult person", "tension", "argument"],
    "failure":      ["fail", "mistake", "wrong", "didn't work", "went wrong", "error"],
    "leadership":   ["lead", "led", "manage", "team", "mentor", "guide", "influence"],
    "ambiguity":    ["unclear", "ambiguous", "no direction", "uncertain", "vague"],
    "initiative":   ["proactive", "without being asked", "on your own", "noticed", "identified"],
    "collaboration":["collaborate", "cross-functional", "partner", "stakeholder", "together"],
    "improvement":  ["improve", "optimize", "better", "faster", "efficient", "process"],
}

# Dynamic STAR example templates keyed by domain
_STAR_TEMPLATES = {
    "conflict": {
        "s": "Our team had a recurring disagreement about code review standards.",
        "t": "I needed to resolve this without creating further friction.",
        "a": "I proposed a team session where each person explained their reasoning, then drafted shared guidelines we all agreed on.",
        "r": "Review turnaround improved by 40% and the friction disappeared within two sprints.",
    },
    "failure": {
        "s": "I shipped a feature that caused a production incident affecting 200 users.",
        "t": "I needed to fix it fast and ensure it never happened again.",
        "a": "I owned the rollback, wrote a post-mortem, and introduced a pre-deploy checklist I got adopted team-wide.",
        "r": "Zero similar incidents in the following 6 months.",
    },
    "leadership": {
        "s": "Our team was blocked on a critical deadline because no one owned the integration layer.",
        "t": "I stepped up to coordinate across three teams.",
        "a": "I ran daily syncs, unblocked dependencies myself where possible, and escalated the right things to management.",
        "r": "We shipped on time. My manager asked me to lead the next cross-team project.",
    },
    "improvement": {
        "s": "Our deployment pipeline took 4 hours and was blocking releases.",
        "t": "I owned CI/CD infrastructure and was asked to reduce that time.",
        "a": "I audited every step, identified 3 redundant stages, and implemented parallelization.",
        "r": "Deployment time dropped from 4 hours to 22 minutes — an 82% reduction.",
    },
    "default": {
        "s": "Describe the context and what problem existed.",
        "t": "Explain what your specific responsibility was.",
        "a": "Walk through exactly what YOU did — step by step.",
        "r": "Quantify the outcome: %, time, users, revenue, reliability.",
    },
}

# Targeted follow-up questions per weakness dimension
_FOLLOWUP_QUESTIONS = {
    "ownership": [
        {
            "question": "What was the specific decision only you made in this situation?",
            "why": "Forces distinction between your contribution and the team's",
            "strong_example": "I decided to rebuild the auth layer from scratch rather than patch it — that was entirely my call.",
        },
        {
            "question": "At what point did you take personal accountability for the outcome?",
            "why": "Tests whether you owned results, not just tasks",
            "strong_example": "When the deadline slipped, I didn't point to blockers — I reprioritized my own work and communicated the new plan.",
        },
    ],
    "initiative": [
        {
            "question": "What would have happened if you hadn't acted?",
            "why": "Reveals whether your action was proactive or reactive",
            "strong_example": "The bug would have hit production Friday — no one else was looking at that part of the stack.",
        },
        {
            "question": "Who asked you to do this, or did you start it yourself?",
            "why": "Direct probe for self-directed vs assigned action",
            "strong_example": "Nobody asked me — I noticed the pattern in our error logs and decided to fix it.",
        },
    ],
    "impact": [
        {
            "question": "How did you measure whether this actually worked?",
            "why": "Tests outcome orientation and quantitative thinking",
            "strong_example": "I tracked P95 latency before and after — dropped from 800ms to 120ms.",
        },
        {
            "question": "What changed for the team or users because of what you did?",
            "why": "Forces concrete downstream impact, not just task completion",
            "strong_example": "Support tickets about that feature dropped 70% the following month.",
        },
    ],
    "structure": [
        {
            "question": "Can you walk me through that again — starting with just the context in one sentence?",
            "why": "Resets the answer into STAR order",
            "strong_example": "Sure — we were a 3-person team, 2 weeks before launch, and our database was timing out under load.",
        },
        {
            "question": "What was the result — in one specific, measurable sentence?",
            "why": "Forces a concrete landing instead of trailing off",
            "strong_example": "We reduced load time by 60% and shipped on time.",
        },
    ],
    "blaming": [
        {
            "question": "Given those constraints, what could YOU have done differently?",
            "why": "Redirects from external blame to personal agency",
            "strong_example": "I could have escalated two weeks earlier instead of waiting for the situation to resolve itself.",
        },
    ],
}


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _count_regex_hits(text: str, patterns: list[str]) -> int:
    return sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))


def _count_all_regex_hits(text: str, patterns: list[str]) -> int:
    return sum(len(re.findall(p, text, re.IGNORECASE)) for p in patterns)


def _first_person_count(text: str) -> int:
    return len(re.findall(r"\b(i|i've|i'd|i'm|i'll)\b", text, re.IGNORECASE))


def _collective_count(text: str) -> int:
    return len(re.findall(r"\b(we|our|us|the team|my team)\b", text, re.IGNORECASE))


def _clamp(v: float, lo: int = 0, hi: int = 10) -> int:
    return max(lo, min(hi, round(v)))


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]


def _normalize_transcript(transcript: Any) -> tuple[list[str], str]:
    """Returns (sentences list, full text)."""
    if isinstance(transcript, list):
        sentences = [
            str(item.get("sentence", "")).strip()
            for item in transcript
            if isinstance(item, dict) and item.get("sentence")
        ]
        return sentences, " ".join(sentences)
    text = str(transcript or "").strip()
    return _split_sentences(text), text


def _detect_question_domain(question: str) -> str:
    q_lower = question.lower()
    for domain, keywords in _QUESTION_DOMAIN_HINTS.items():
        if any(kw in q_lower for kw in keywords):
            return domain
    return "default"


def _detect_star_sequence(sentences: list[str]) -> dict[str, Any]:
    """Sentence-level STAR phase detection with order checking."""
    phase_positions: dict[str, int] = {}
    sentence_phases: list[str | None] = []

    for i, sent in enumerate(sentences):
        matched = None
        for phase, patterns in _STAR_PHASES.items():
            if any(re.search(p, sent, re.IGNORECASE) for p in patterns):
                matched = phase
                break
        sentence_phases.append(matched)
        if matched and matched not in phase_positions:
            phase_positions[matched] = i

    phases_detected = list(dict.fromkeys(p for p in sentence_phases if p))
    correct_order = ["situation", "task", "action", "result"]
    detected_ordered = [p for p in correct_order if p in phase_positions]
    positions = [phase_positions[p] for p in detected_ordered]
    order_correct = positions == sorted(positions)

    coverage = len(set(phases_detected) & set(correct_order))
    score = _clamp(coverage * 2 + (2 if order_correct else 0))

    return {
        "sequence_score": score,
        "phases_detected": phases_detected,
        "order_correct": order_correct,
        "missing_phases": [p for p in correct_order if p not in phases_detected],
    }


# ---------------------------------------------------------------------------
# SCORING FUNCTIONS  (tension model — positive vs negative signals)
# ---------------------------------------------------------------------------

def _score_ownership(strong: int, weak: int, blaming: int, i_ratio: float, we_ratio: float) -> int:
    pos = strong * 2.5 + min(i_ratio * 30, 4.0)
    neg = weak * 1.0 + blaming * 4.0 + max(0, (we_ratio - i_ratio) * 10)
    return _clamp(5.0 + pos - neg)


def _score_initiative(hits: int, weak: int, i_ratio: float) -> int:
    pos = hits * 2.0 + min(i_ratio * 20, 3.0)
    neg = weak * 0.5
    return _clamp(5.0 + pos - neg)


def _score_impact(hits: int, has_metrics: bool, result_present: bool) -> int:
    pos = hits * 1.5 + (3.0 if has_metrics else 0.0) + (1.0 if result_present else 0.0)
    neg = 0.0 if hits > 0 else 2.0
    return _clamp(4.0 + pos - neg)


def _score_structure(seq_score: int, n_sentences: int, fillers: int) -> int:
    base = float(seq_score)
    if n_sentences > 12: base -= 2
    elif n_sentences > 9: base -= 1
    elif n_sentences < 3: base -= 2
    base -= min(fillers, 3)
    return _clamp(base)


def _score_clarity(filler_hits: int, n_sentences: int, total_words: int) -> int:
    """
    Clarity: how clean and direct the delivery is.
    Penalizes filler density and extreme length.
    """
    filler_density = filler_hits / max(total_words / 10, 1)  # per 10 words
    base = 10.0 - (filler_density * 3) - (1 if n_sentences > 10 else 0)
    return _clamp(base)


def _score_relevance(text_lower: str, question: str, domain: str) -> int:
    """
    Relevance: does the answer address the actual question domain?
    Checks for domain keywords in the answer — not a trivial word match.
    """
    domain_keywords = _QUESTION_DOMAIN_HINTS.get(domain, [])
    if not domain_keywords:
        return 7  # unknown domain — neutral

    hits = sum(1 for kw in domain_keywords if kw in text_lower)
    # Also reward if question's main verb appears
    q_words = set(question.lower().split())
    answer_words = set(text_lower.split())
    overlap = len(q_words & answer_words & {
        "conflict", "fail", "lead", "improve", "challenge",
        "difficult", "initiative", "collaborate", "mistake"
    })
    return _clamp(5 + hits * 1.5 + overlap * 1.0)


def _score_specificity(text_lower: str, has_metrics: bool, strong_hits: int) -> int:
    """
    Specificity: does the answer use concrete details?
    """
    specific_markers = [
        r"\bspecifically\b", r"\bfor example\b", r"\bfor instance\b",
        r"\bin particular\b", r"\bexactly\b",
        r"\b(monday|tuesday|wednesday|sprint|q[1-4]|v\d)\b",  # time refs
        r"\b(postgres|redis|aws|python|react|kubernetes)\b",   # tech refs
    ]
    hits = _count_regex_hits(text_lower, specific_markers)
    base = 5.0 + hits * 1.5 + (2.0 if has_metrics else 0.0) + (strong_hits * 0.5)
    return _clamp(base)


# ---------------------------------------------------------------------------
# SENTENCE-LEVEL FEEDBACK  (prioritized, not truncated arbitrarily)
# ---------------------------------------------------------------------------

def _analyze_sentences(sentences: list[str]) -> list[dict]:
    """
    Score each sentence and return the top weakest ones,
    ordered by severity — not by position.
    """
    scored = []
    for idx, sent in enumerate(sentences):
        s = sent.lower()
        issues = []
        severity = 0

        if _count_regex_hits(s, BLAMING_PATTERNS) > 0:
            issues.append("blaming_language")
            severity += 3

        if _count_regex_hits(s, WEAK_OWNERSHIP_PATTERNS) > 0:
            issues.append("weak_ownership")
            severity += 2

        if ("improve" in s or "result" in s or "impact" in s) and not re.search(r"\d", s):
            issues.append("vague_impact")
            severity += 2

        filler_count = _count_all_regex_hits(s, FILLER_PATTERNS)
        if filler_count >= 2:
            issues.append("high_filler")
            severity += 1

        if len(s.split()) < 5 and idx > 0:
            issues.append("too_vague")
            severity += 1

        if issues:
            scored.append({
                "idx": idx,
                "sentence": sent,
                "issues": issues,
                "severity": severity,
                "coaching": _sentence_coaching(issues, sent),
            })

    # Return top 4 by severity — most impactful first
    return sorted(scored, key=lambda x: -x["severity"])[:4]


def _sentence_coaching(issues: list[str], sentence: str) -> str:
    if "blaming_language" in issues:
        return "Reframe: instead of attributing fault externally, describe what you navigated. 'I worked around the constraint by...'"
    if "weak_ownership" in issues:
        return "Replace passive contribution ('helped', 'was involved') with a direct action: 'I designed...', 'I led...', 'I built...'"
    if "vague_impact" in issues:
        return "Add a number to this outcome — even an estimate counts: '...which reduced X by roughly 30%.'"
    if "high_filler" in issues:
        return "Remove filler words ('kind of', 'basically', 'I guess') — they signal uncertainty about your own story."
    if "too_vague" in issues:
        return "Expand this sentence — what specifically did you do here? One more concrete detail makes a difference."
    return "Make this sentence more specific and direct."


# ---------------------------------------------------------------------------
# ADAPTIVE COACHING LAYER
# ---------------------------------------------------------------------------

def _select_followup_questions(
    ownership: int,
    initiative: int,
    impact: int,
    structure: int,
    blaming_hits: int,
) -> list[dict]:
    """
    Select follow-up questions based on actual weak dimensions,
    ordered by severity. Returns 2 most important.
    """
    candidates: list[tuple[int, str]] = []  # (priority, dimension)

    if blaming_hits > 0:
        candidates.append((0, "blaming"))  # highest priority
    if ownership < 6:
        candidates.append((1, "ownership"))
    if impact < 6:
        candidates.append((2, "impact"))
    if initiative < 6:
        candidates.append((3, "initiative"))
    if structure < 5:
        candidates.append((4, "structure"))

    candidates.sort(key=lambda x: x[0])
    selected = []
    seen_dims = set()

    for _, dim in candidates:
        if dim not in seen_dims and dim in _FOLLOWUP_QUESTIONS:
            selected.extend(_FOLLOWUP_QUESTIONS[dim][:1])  # 1 per dimension
            seen_dims.add(dim)
        if len(selected) >= 2:
            break

    # Fallback if nothing weak
    if not selected:
        selected = [{
            "question": "Walk me through the single most impactful thing you personally did.",
            "why": "Deepens any strong answer",
            "strong_example": "I refactored the core query layer — that one change cut our P95 latency in half.",
        }]

    return selected


def _determine_training_mode(
    ownership: int, initiative: int, impact: int, structure: int, blaming_hits: int
) -> str:
    """
    Determine primary coaching mode based on the weakest dimension.
    Fixed the original bug where sequential if-blocks overwrote each other.
    """
    if blaming_hits > 0:
        return "accountability_training"

    scores = {
        "structure_training":  structure,
        "ownership_training":  ownership,
        "impact_training":     impact,
        "initiative_training": initiative,
    }
    # Return mode for the lowest scoring dimension
    return min(scores, key=lambda k: scores[k])


def _build_feedback(
    ownership: int, initiative: int, impact: int,
    structure: int, blaming_hits: int,
    flags: list[str], domain: str,
) -> str:
    parts = []

    if blaming_hits > 0:
        parts.append(
            "Critical: remove blame attribution. Interviewers mark this down heavily. "
            "Reframe as 'I navigated X constraint' instead of 'they caused Y.'"
        )
    if ownership < 6:
        parts.append("Increase ownership signal: use 'I decided', 'I led', 'my approach was'.")
    if impact < 6:
        parts.append("Add a measurable result — even an estimate ('roughly 30% faster') beats a vague outcome.")
    if initiative < 6:
        parts.append("Show proactivity: describe what you started without being asked.")
    if structure < 5:
        parts.append("Structure your answer: Situation (1 sentence) → Task → Action → Result.")

    # Domain-specific tip
    domain_tips = {
        "conflict":  "For conflict questions: name the disagreement directly. Vagueness reads as avoidance.",
        "failure":   "For failure questions: the learning and what you changed matters more than the mistake itself.",
        "leadership":"For leadership questions: show how you influenced people, not just what tasks you completed.",
        "ambiguity": "For ambiguity questions: show how you made a decision with incomplete information.",
    }
    if domain in domain_tips and not parts:
        parts.append(domain_tips[domain])

    if not parts:
        parts.append(
            "Strong answer. Clear ownership, initiative, and measurable impact are all present. "
            "Structure follows STAR order."
        )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# PUBLIC INTERFACE
# ---------------------------------------------------------------------------

def analyze_behavioral_answer_fallback(
    transcript: list[dict] | str,
    question: str,
) -> dict[str, Any]:
    """
    Deterministic behavioral interview analysis.
    Designed as a fallback for when the AI analyzer quota is exhausted.
    Adaptive outputs — coaching, questions, and examples adjust to the
    actual answer, not static templates.
    """

    sentences, transcript_text = _normalize_transcript(transcript)
    text_lower = transcript_text.lower()
    total_words = len(text_lower.split()) or 1

    # --- Domain detection (makes coaching question-aware) ---
    domain = _detect_question_domain(question)

    # --- Signal extraction ---
    blaming_hits    = _count_regex_hits(text_lower, BLAMING_PATTERNS)
    strong_hits     = _count_regex_hits(text_lower, STRONG_OWNERSHIP_PATTERNS)
    weak_hits       = _count_all_regex_hits(text_lower, WEAK_OWNERSHIP_PATTERNS)
    initiative_hits = _count_regex_hits(text_lower, INITIATIVE_PATTERNS)
    impact_hits     = _count_regex_hits(text_lower, IMPACT_PATTERNS)
    filler_hits     = _count_all_regex_hits(text_lower, FILLER_PATTERNS)
    has_metrics     = bool(re.search(r"\b\d+\s*(%|percent|x\b|times|hours?|days?|\$)", text_lower))

    i_count  = _first_person_count(text_lower)
    we_count = _collective_count(text_lower)
    i_ratio  = i_count / total_words
    we_ratio = we_count / total_words

    # --- STAR sequence analysis ---
    star = _detect_star_sequence(sentences)
    result_present = "result" in star["phases_detected"]

    # --- Scores ---
    ownership  = _score_ownership(strong_hits, weak_hits, blaming_hits, i_ratio, we_ratio)
    initiative = _score_initiative(initiative_hits, weak_hits, i_ratio)
    impact     = _score_impact(impact_hits, has_metrics, result_present)
    structure  = _score_structure(star["sequence_score"], len(sentences), filler_hits)
    clarity    = _score_clarity(filler_hits, len(sentences), total_words)
    relevance  = _score_relevance(text_lower, question, domain)
    specificity= _score_specificity(text_lower, has_metrics, strong_hits)

    # --- Overall (weighted) ---
    overall = round(
        ownership   * 0.25 +
        initiative  * 0.20 +
        impact      * 0.20 +
        structure   * 0.15 +
        clarity     * 0.10 +
        relevance   * 0.05 +
        specificity * 0.05,
        1
    )

    # --- Pass/fail ---
    passed = (
        ownership  >= 6 and
        initiative >= 6 and
        impact     >= 6 and
        structure  >= 5 and
        blaming_hits == 0
    )

    # --- Flags ---
    flags = []
    if blaming_hits > 0:        flags.append("blaming_language")
    if not has_metrics:         flags.append("no_measurable_impact")
    if len(sentences) > 12:     flags.append("rambling_response")
    if filler_hits >= 4:        flags.append("high_filler_density")
    if star["missing_phases"]:  flags.append("incomplete_star")
    if we_ratio > 0.5 and i_ratio < 0.08: flags.append("low_ownership_signal")

    # --- Adaptive outputs ---
    sentence_feedback  = _analyze_sentences(sentences)
    followup_questions = _select_followup_questions(ownership, initiative, impact, structure, blaming_hits)
    training_mode      = _determine_training_mode(ownership, initiative, impact, structure, blaming_hits)
    star_example       = _STAR_TEMPLATES.get(domain, _STAR_TEMPLATES["default"])
    feedback           = _build_feedback(ownership, initiative, impact, structure, blaming_hits, flags, domain)

    return {
        "overall_score": overall,
        "passed": passed,
        "analyzer": "deterministic_fallback",
        "question_domain": domain,

        "scores": {
            "ownership":   ownership,
            "initiative":  initiative,
            "impact":      impact,
            "structure":   structure,
            "clarity":     clarity,
            "relevance":   relevance,
            "specificity": specificity,
        },

        "star_analysis": {
            "sequence_score":  star["sequence_score"],
            "phases_detected": star["phases_detected"],
            "order_correct":   star["order_correct"],
            "missing_phases":  star["missing_phases"],
        },

        "signals": {
            "i_ratio":           round(i_ratio, 3),
            "we_ratio":          round(we_ratio, 3),
            "has_metrics":       has_metrics,
            "strong_ownership":  strong_hits,
            "weak_ownership":    weak_hits,
            "blaming":           blaming_hits,
            "initiative_hits":   initiative_hits,
            "impact_hits":       impact_hits,
            "filler_hits":       filler_hits,
            "sentence_count":    len(sentences),
            "word_count":        total_words,
        },

        "flags": flags,
        "feedback": feedback,

        # Adaptive — changes based on actual weak dimensions
        "followup_questions":  followup_questions,
        "primary_training_mode": training_mode,

        # Dynamic — matches question domain
        "star_example": star_example,

        # Prioritized sentence feedback — worst sentences first
        "sentence_feedback": sentence_feedback,

        "transcript": transcript_text,
        "rubric_version": "fallback_2.0",
    }
