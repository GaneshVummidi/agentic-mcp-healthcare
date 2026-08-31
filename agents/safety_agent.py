"""
Agent 2: Safety Agent
  - Risk assessment
  - Detect harmful queries
  - Emergency detection
  - Apply guardrails
"""
import re

EMERGENCY_PATTERNS = [
    r"\bchest pain\b", r"\bcan.?t breathe\b", r"\bnot breathing\b",
    r"\bsevere bleeding\b", r"\bunconscious\b", r"\bsuicid", r"\bstroke\b",
    r"\bheart attack\b", r"\boverdose\b", r"\bpoison(ed|ing)?\b",
]

HARMFUL_PATTERNS = [
    r"\bhow (to|do i) (make|synthesize) .*(drug|poison|explosive)",
    r"\blethal dose\b",
    r"\bhow to (harm|hurt|kill) (myself|someone)",
]

EMERGENCY_MESSAGE = (
    "This may be a medical emergency. Please call your local emergency number "
    "immediately (e.g., 911 in the US, 112 in the EU) or go to the nearest "
    "emergency department. If you or someone else may be in danger, do not wait."
)

BLOCKED_MESSAGE = (
    "I can't help with that request. If you're going through a difficult time, "
    "please reach out to a mental health professional or a crisis line in your area."
)


def assess(query: str) -> dict:
    q = query.lower()

    is_emergency = any(re.search(p, q) for p in EMERGENCY_PATTERNS)
    is_harmful = any(re.search(p, q) for p in HARMFUL_PATTERNS)

    if is_emergency:
        risk_level = "critical"
    elif is_harmful:
        risk_level = "blocked"
    elif any(w in q for w in ["pain", "bleeding", "fever", "infection"]):
        risk_level = "elevated"
    else:
        risk_level = "low"

    return {
        "risk_level": risk_level,
        "is_emergency": is_emergency,
        "is_blocked": is_harmful,
        "guardrail_message": EMERGENCY_MESSAGE if is_emergency else (BLOCKED_MESSAGE if is_harmful else None),
    }
