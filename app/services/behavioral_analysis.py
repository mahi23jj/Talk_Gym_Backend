"""
Behavioral Interview Analysis Engine
Rule-based signal extraction + rubric scoring.
No LLM in this layer — all deterministic.
"""

from __future__ import annotations
import re
from typing import Any
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# PHRASE LIBRARIES  (expand these over time — the richer these are, the
# stronger the engine.  Each entry is a regex pattern for flexibility.)
# ---------------------------------------------------------------------------

# Blaming — passive deflection, externalizing failure
_BLAMING_PATTERNS = [
    r"\bthey (made|forced|told|caused|blocked|prevented)\b",
    r"\bit was (their|his|her|the team'?s?) fault\b",
    r"\bmy manager (blocked|refused|wouldn'?t|didn'?t allow)\b",
    r"\bwe had no choice\b",
    r"\bthe situation forced\b",
    r"\bno one (told|informed|warned) me\b",
    r"\bi wasn'?t (told|informed|given)\b",
    r"\bthey never\b",
    r"\bnobody (helped|supported|cared)\b",
    r"\bit wasn'?t (really )?my (fault|responsibility|job)\b",
    r"\bout of my (hands|control)\b",
    r"\bwas forced to\b",
]

# Strong ownership — first-person decisive action
_STRONG_OWNERSHIP_PATTERNS = [
    r"\bi (decided|chose|initiated|drove|led|owned|took ownership)\b",
    r"\bi made the (decision|call|choice)\b",
    r"\bi (proposed|designed|built|created|implemented|architected)\b",
    r"\bi (stepped up|volunteered|raised|flagged|escalated)\b",
    r"\bi took (responsibility|the lead|initiative|charge)\b",
    r"\bmy (decision|idea|proposal|approach|solution)\b",
    r"\bi (realized|noticed|identified|spotted|recognized) (the problem|an issue|a gap|an opportunity)\b",
    r"\bi (pushed|advocated|argued) for\b",
    r"\bi was responsible for\b",
    r"\bi held myself\b",
]

# Weak ownership — passive, vague, deflecting credit
_WEAK_OWNERSHIP_PATTERNS = [
    r"\bwe (all|just|kind of|sort of|basically|pretty much)\b",
    r"\bsomeone (else|on the team)\b",
    r"\bit (just|kind of|sort of) (happened|worked out|came together)\b",
    r"\bthings (worked out|fell into place)\b",
    r"\bwe were (told|asked|required|supposed to)\b",
    r"\bjust followed\b",
    r"\bnot (really )?sure (why|how|who)\b",
    r"\bkind of\b",
    r"\bsort of\b",
    r"\bbasically\b",
    r"\bmaybe i\b",
    r"\bi guess\b",
    r"\bi think i\b",  # hedging on own actions
]

# Initiative — proactive, self-directed behavior
_INITIATIVE_PATTERNS = [
    r"\bi (proactively|independently|voluntarily)\b",
    r"\bwithout (being asked|being told|direction|prompting)\b",
    r"\bon my own (initiative|accord)\b",
    r"\bi (identified|spotted|noticed) (the problem|an issue|an opportunity|a gap) (before|early|ahead)\b",
    r"\bi (proposed|suggested|recommended) (a|the|this|an)\b",
    r"\bi (reached out|contacted|approached) (to|the|them)\b",
    r"\bi (set up|created|established|built) (a|the|this|an)\b",
    r"\bi didn'?t wait\b",
    r"\bi (went ahead|moved forward|took action) (without|before|ahead)\b",
    r"\bi (started|began|kicked off|launched)\b",
]

# Impact — measurable, outcome-oriented language
_IMPACT_PATTERNS = [
    r"\b\d+\s*(%|percent|x|times faster|times better|hours?|days?|weeks?)\b",
    r"\breduced (by|from|the)\b",
    r"\bincreased (by|from|the)\b",
    r"\bimproved (by|from|the)\b",
    r"\bsaved ([\$\d]|\btime\b|\bmoney\b|\bhours?\b)\b",
    r"\bgrew (by|from|to)\b",
    r"\bcut ([\$\d]|\btime\b|\bcosts?\b|the)\b",
    r"\bdelivered (on time|early|ahead|under budget|within)\b",
    r"\bthe (result|outcome|impact) was\b",
    r"\bas a result\b",
    r"\bwhich (led to|resulted in|meant that|allowed|enabled)\b",
    r"\bwe (shipped|launched|released|deployed|completed)\b",
    r"\bsuccessfully\b",
]

# STAR structural markers — context-setting, action, outcome signals
# Keyed by phase for sequence analysis
_STAR_PHASE_PATTERNS = {
    "situation": [
        r"\b(at the time|back then|this was|we were|i was working|the context|the background)\b",
        r"\b(the (problem|challenge|situation|issue) was\b)",
        r"\bwe (had|faced|were dealing with|were trying to)\b",
        r"\bour (team|company|product|system) (was|had|needed)\b",
    ],
    "task": [
        r"\bmy (role|job|responsibility|goal|objective|task) was\b",
        r"\bi (was responsible for|was asked to|needed to|had to)\b",
        r"\bthe (goal|objective|target|requirement) was\b",
        r"\bwhat (i needed to do|was needed|was required)\b",
    ],
    "action": [
        r"\bi (decided|chose|started|began|built|designed|implemented|wrote|created)\b",
        r"\bfirst[,\s] i\b",
        r"\bthe (first|next|final) (step|thing) (i|was)\b",
        r"\bi then\b",
        r"\bso i\b",
        r"\bmy approach was\b",
        r"\bspecifically[,\s] i\b",
    ],
    "result": [
        r"\bas a result\b",
        r"\bthe (result|outcome|impact|effect) (was|is|has been)\b",
        r"\bin the end\b",
        r"\bultimately\b",
        r"\bwe (achieved|reached|hit|exceeded|delivered|shipped)\b",
        r"\bthis (led to|resulted in|meant|allowed|enabled)\b",
        r"\bafter (this|that|the change|implementing)\b",
    ],
}

# Filler / hedging — delivery quality signals (text side)
_FILLER_PATTERNS = [
    r"\b(um|uh|like|you know|basically|literally|honestly|right\?|so yeah)\b",
    r"\bkind of\b",
    r"\bsort of\b",
    r"\bi mean\b",
    r"\bif that makes sense\b",
    r"\bdoes that make sense\b",
]


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _count_pattern_hits(text: str, patterns: list[str]) -> int:
    """Count distinct pattern matches across all patterns."""
    return sum(
        1 for p in patterns
        if re.search(p, text, re.IGNORECASE)
    )


def _count_all_hits(text: str, patterns: list[str]) -> int:
    """Count total match instances (not just distinct patterns)."""
    total = 0
    for p in patterns:
        total += len(re.findall(p, text, re.IGNORECASE))
    return total


def _count_first_person(text: str) -> int:
    """
    Robust first-person count: I, I've, I'd, I'm, I'll, I'd, I've.
    Uses word boundary to avoid false positives.
    """
    return len(re.findall(
        r"\b(i|i've|i'd|i'm|i'll|i'?ve|i'?d)\b",
        text, re.IGNORECASE
    ))


def _count_collective(text: str) -> int:
    """Count we/our/us/team — collective vs individual signal."""
    return len(re.findall(
        r"\b(we|our|us|the team|my team)\b",
        text, re.IGNORECASE
    ))


def _clamp(score: float, lo: int = 0, hi: int = 10) -> int:
    return max(lo, min(hi, round(score)))


def _detect_star_sequence(sentences: list[str]) -> dict[str, Any]:
    """
    Analyze STAR structure by sentence position, not keyword presence.

    A well-structured answer puts situation/task early, action in the
    middle, result at the end. We score based on whether the phases
    appear in the right order and with appropriate proportion.
    """
    n = len(sentences)
    if n == 0:
        return {"sequence_score": 0, "phases_detected": [], "order_correct": False}

    # Assign each sentence to a STAR phase (first match wins)
    sentence_phases: list[str | None] = []
    for sent in sentences:
        matched = None
        for phase, patterns in _STAR_PHASE_PATTERNS.items():
            if any(re.search(p, sent, re.IGNORECASE) for p in patterns):
                matched = phase
                break
        sentence_phases.append(matched)

    phases_detected = [p for p in sentence_phases if p is not None]
    unique_phases = list(dict.fromkeys(phases_detected))  # ordered unique

    # Check if phases appear in correct S→T→A→R order
    correct_order = ["situation", "task", "action", "result"]
    order_correct = False

    if len(unique_phases) >= 2:
        # Get positions of first occurrence of each detected phase
        phase_positions = {}
        for i, phase in enumerate(sentence_phases):
            if phase and phase not in phase_positions:
                phase_positions[phase] = i

        # Check ordering of detected phases
        detected_in_correct = [
            p for p in correct_order if p in phase_positions
        ]
        positions_in_order = [phase_positions[p] for p in detected_in_correct]
        order_correct = positions_in_order == sorted(positions_in_order)

    # Score: phases coverage + ordering bonus
    coverage_score = len(set(phases_detected) & set(correct_order)) * 2  # 0–8
    order_bonus = 2 if order_correct else 0
    sequence_score = _clamp(coverage_score + order_bonus)

    return {
        "sequence_score": sequence_score,
        "phases_detected": unique_phases,
        "order_correct": order_correct,
        "phase_map": sentence_phases,
    }


def _score_ownership(
    text: str,
    i_ratio: float,
    we_ratio: float,
    strong_hits: int,
    weak_hits: int,
    blaming_hits: int,
) -> int:
    """
    Ownership rubric — models the tension between strong and weak signals
    rather than starting from an arbitrary midpoint.

    Positive signals pull toward 10, negative signals pull toward 0.
    The ratio between them determines the final score.
    """
    positive = (
        strong_hits * 2.5 +
        min(i_ratio * 30, 4.0)   # cap contribution from raw ratio
    )
    negative = (
        weak_hits * 1.0 +
        blaming_hits * 4.0 +     # blaming is a hard negative signal
        max(0, (we_ratio - i_ratio) * 10)  # heavy "we" without "I" is a flag
    )
    raw = 5.0 + positive - negative
    return _clamp(raw)


def _score_initiative(
    text: str,
    initiative_hits: int,
    weak_hits: int,
    i_ratio: float,
) -> int:
    positive = initiative_hits * 2.0 + min(i_ratio * 20, 3.0)
    negative = weak_hits * 0.5
    return _clamp(5.0 + positive - negative)


def _score_impact(
    text: str,
    impact_hits: int,
    has_metrics: bool,
    result_phase_present: bool,
) -> int:
    positive = (
        impact_hits * 1.5 +
        (3.0 if has_metrics else 0.0) +
        (1.0 if result_phase_present else 0.0)
    )
    negative = 0.0 if impact_hits > 0 else 2.0  # penalty for no impact language
    return _clamp(4.0 + positive - negative)


def _score_structure(
    sequence_score: int,
    sentence_count: int,
    filler_hits: int,
) -> int:
    base = sequence_score  # 0–10 from STAR sequence analysis
    # Length penalties
    if sentence_count > 12:
        base -= 2   # significant rambling
    elif sentence_count > 9:
        base -= 1   # mild rambling
    elif sentence_count < 3:
        base -= 2   # too short to assess structure
    # Filler penalty
    base -= min(filler_hits, 3)
    return _clamp(base)


# ---------------------------------------------------------------------------
# EXPLAINABILITY LAYER
# ---------------------------------------------------------------------------

@dataclass
class AnalysisFlag:
    code: str
    severity: str          # "critical" | "warning" | "info"
    message: str
    coaching_hint: str


def _build_flags(
    blaming_hits: int,
    we_ratio: float,
    i_ratio: float,
    has_metrics: bool,
    sentence_count: int,
    filler_hits: int,
    phases_detected: list[str],
    order_correct: bool,
    ownership: int,
    initiative: int,
    impact: int,
) -> list[AnalysisFlag]:
    flags: list[AnalysisFlag] = []

    if blaming_hits > 0:
        flags.append(AnalysisFlag(
            code="blaming_language",
            severity="critical",
            message=f"Detected {blaming_hits} instance(s) of blame externalization.",
            coaching_hint="Reframe using 'I navigated' or 'I worked around' instead of attributing failure outward."
        ))

    if we_ratio > 0.5 and i_ratio < 0.08:
        flags.append(AnalysisFlag(
            code="low_ownership_signal",
            severity="critical",
            message="Heavy collective language ('we/our/team') with very little first-person ownership.",
            coaching_hint="Replace 'we decided' with 'I proposed and the team aligned' to claim your contribution clearly."
        ))

    if not has_metrics:
        flags.append(AnalysisFlag(
            code="no_measurable_impact",
            severity="warning",
            message="No quantified outcomes detected.",
            coaching_hint="Add at least one number: %, time saved, users affected, revenue impacted."
        ))

    if sentence_count > 12:
        flags.append(AnalysisFlag(
            code="rambling_response",
            severity="warning",
            message=f"Response is {sentence_count} sentences — likely exceeds 2-minute target.",
            coaching_hint="Trim situation/task to 1-2 sentences. Action should be specific, not exhaustive."
        ))

    if filler_hits >= 4:
        flags.append(AnalysisFlag(
            code="high_filler_density",
            severity="warning",
            message=f"Detected {filler_hits} filler words/phrases.",
            coaching_hint="Replace 'kind of', 'basically', 'I guess' with assertive language."
        ))

    missing_phases = [
        p for p in ["situation", "task", "action", "result"]
        if p not in phases_detected
    ]
    if missing_phases:
        flags.append(AnalysisFlag(
            code="incomplete_star",
            severity="warning" if len(missing_phases) == 1 else "critical",
            message=f"Missing STAR phases: {', '.join(missing_phases)}.",
            coaching_hint=f"Add a clear {missing_phases[0]} section. Interviewers need all four phases to evaluate your story."
        ))

    if len(phases_detected) >= 3 and not order_correct:
        flags.append(AnalysisFlag(
            code="star_order_incorrect",
            severity="info",
            message="STAR phases present but appear out of sequence.",
            coaching_hint="Lead with situation → task → action → result. Jumping to action before context confuses the listener."
        ))

    if initiative < 5:
        flags.append(AnalysisFlag(
            code="low_initiative_signal",
            severity="warning",
            message="Limited proactive behavior language detected.",
            coaching_hint="Add phrases like 'I proactively', 'without being asked', 'I identified the gap before it became a problem'."
        ))

    return flags


# ---------------------------------------------------------------------------
# FEEDBACK GENERATOR  (still deterministic — no LLM)
# ---------------------------------------------------------------------------

def _build_feedback(
    ownership: int,
    initiative: int,
    impact: int,
    structure: int,
    flags: list[AnalysisFlag],
) -> str:
    parts = []

    # Lead with critical flags
    critical = [f for f in flags if f.severity == "critical"]
    for flag in critical[:2]:  # top 2 critical only
        parts.append(flag.coaching_hint)

    # Score-based coaching for non-critical dimensions
    if ownership < 6 and not any(f.code in ["blaming_language", "low_ownership_signal"] for f in critical):
        parts.append("Increase ownership: use 'I decided', 'I chose', 'my approach was' instead of passive or collective framing.")

    if initiative < 6 and "low_initiative_signal" not in [f.code for f in flags]:
        parts.append("Show initiative: describe what you started without being asked, or what problem you spotted before others.")

    if impact < 6:
        parts.append("Strengthen impact: quantify the outcome. Even an estimate ('roughly 30% faster') is better than no number.")

    if structure < 5:
        parts.append("Improve structure: use the STAR format — Situation, Task, Action, Result — in that order.")

    if not parts:
        parts.append(
            "Strong behavioral signal. Clear ownership, initiative, and measurable impact are all present. "
            "Answer is well-structured and direct."
        )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# PUBLIC INTERFACE
# ---------------------------------------------------------------------------

def analyze_behavioral_answer(
    transcript: list[dict] | str,
    question: str,
) -> dict[str, Any]:
    """
    Analyze a behavioral interview answer.

    Args:
        transcript: Either a list of {"sentence": str} dicts
                    or a raw string.
        question:   The interview question being answered.

    Returns:
        Structured analysis dict with scores, flags, and coaching.
    """

    # --- Normalize input ---
    if isinstance(transcript, str):
        sentences = [s.strip() for s in re.split(r"[.!?]+", transcript) if s.strip()]
        transcript_text = transcript.strip()
    else:
        sentences = [item["sentence"] for item in transcript if item.get("sentence")]
        transcript_text = " ".join(sentences)

    text = transcript_text  # preserve case for some checks, lowercase below
    text_lower = text.lower()

    # --- Signal extraction ---
    has_metrics = bool(re.search(r"\b\d+\s*(%|percent|x\b|times|hours?|days?|weeks?|\$)", text_lower))

    blaming_hits    = _count_pattern_hits(text_lower, _BLAMING_PATTERNS)
    strong_hits     = _count_pattern_hits(text_lower, _STRONG_OWNERSHIP_PATTERNS)
    weak_hits       = _count_all_hits(text_lower, _WEAK_OWNERSHIP_PATTERNS)
    initiative_hits = _count_pattern_hits(text_lower, _INITIATIVE_PATTERNS)
    impact_hits     = _count_pattern_hits(text_lower, _IMPACT_PATTERNS)
    filler_hits     = _count_all_hits(text_lower, _FILLER_PATTERNS)

    total_words = len(text_lower.split()) or 1
    i_count     = _count_first_person(text_lower)
    we_count    = _count_collective(text_lower)
    i_ratio     = i_count / total_words
    we_ratio    = we_count / total_words

    # --- STAR sequence analysis ---
    star = _detect_star_sequence(sentences)
    result_present = "result" in star["phases_detected"]

    # --- Rubric scoring ---
    ownership  = _score_ownership(text_lower, i_ratio, we_ratio, strong_hits, weak_hits, blaming_hits)
    initiative = _score_initiative(text_lower, initiative_hits, weak_hits, i_ratio)
    impact     = _score_impact(text_lower, impact_hits, has_metrics, result_present)
    structure  = _score_structure(star["sequence_score"], len(sentences), filler_hits)

    # --- Flags ---
    flags = _build_flags(
        blaming_hits, we_ratio, i_ratio, has_metrics,
        len(sentences), filler_hits,
        star["phases_detected"], star["order_correct"],
        ownership, initiative, impact,
    )

    # --- Pass/fail gate ---
    critical_flags = [f.code for f in flags if f.severity == "critical"]
    passed = (
        ownership  >= 6 and
        initiative >= 6 and
        impact     >= 6 and
        structure  >= 5 and
        not critical_flags
    )

    # --- Overall score (weighted) ---
    overall = round(
        ownership  * 0.30 +
        initiative * 0.25 +
        impact     * 0.25 +
        structure  * 0.20,
        1
    )

    # --- Feedback ---
    feedback = _build_feedback(ownership, initiative, impact, structure, flags)

    return {
        "overall_score": overall,
        "passed": passed,

        "scores": {
            "ownership":  ownership,
            "initiative": initiative,
            "impact":     impact,
            "structure":  structure,
        },

        "star_analysis": {
            "sequence_score":  star["sequence_score"],
            "phases_detected": star["phases_detected"],
            "order_correct":   star["order_correct"],
        },

        "signals": {
            "i_ratio":       round(i_ratio, 3),
            "we_ratio":      round(we_ratio, 3),
            "has_metrics":   has_metrics,
            "strong_ownership_hits": strong_hits,
            "weak_ownership_hits":   weak_hits,
            "blaming_hits":          blaming_hits,
            "initiative_hits":       initiative_hits,
            "impact_hits":           impact_hits,
            "filler_hits":           filler_hits,
            "sentence_count":        len(sentences),
        },

        "flags": [
            {
                "code":          f.code,
                "severity":      f.severity,
                "message":       f.message,
                "coaching_hint": f.coaching_hint,
            }
            for f in flags
        ],

        "feedback": feedback,
        "question": question,
        "transcript": transcript_text,
        "rubric_version": "3.0",
    }
