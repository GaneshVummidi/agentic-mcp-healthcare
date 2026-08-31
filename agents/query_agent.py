"""
Agent 1: Query Agent
  - Understands user query
  - Intent detection
  - Extract key entities
  - Determine required tools
"""
import re

INTENTS = {
    "drug_info": [r"\bdrug\b", r"\bmedicine\b", r"\bmedication\b", r"\bdosage\b", r"\bside effect"],
    "disease_info": [r"\bdisease\b", r"\bcondition\b", r"\bsymptom", r"\bdiagnos", r"\bwhat is\b"],
    "emergency": [r"\bemergency\b", r"\bchest pain\b", r"\bcan.?t breathe\b", r"\bsuicid", r"\bsevere bleeding\b"],
    "greeting": [r"^\s*(hi|hello|hey)\b"],
    "general_health": [],  # fallback
}

KNOWN_ENTITIES = [
    "flu", "influenza", "hypertension", "high blood pressure", "diabetes",
    "aspirin", "ibuprofen", "paracetamol", "acetaminophen", "metformin",
]


def detect_intent(query: str) -> str:
    q = query.lower()
    for intent, patterns in INTENTS.items():
        for p in patterns:
            if re.search(p, q):
                return intent
    return "general_health"


def extract_entities(query: str) -> list[str]:
    q = query.lower()
    return [e for e in KNOWN_ENTITIES if e in q]


def determine_required_tools(intent: str, entities: list[str]) -> list[str]:
    tools = ["database"]  # always check cache / history first
    if intent == "drug_info" or any(e in ["aspirin", "ibuprofen", "paracetamol", "acetaminophen", "metformin"] for e in entities):
        tools.append("medical_api:drug")
    if intent in ("disease_info", "general_health") or any(
        e in ["flu", "influenza", "hypertension", "high blood pressure", "diabetes"] for e in entities
    ):
        tools.append("medical_api:disease")
    tools.append("web_search")
    return tools


def analyze(query: str) -> dict:
    intent = detect_intent(query)
    entities = extract_entities(query)
    required_tools = determine_required_tools(intent, entities)
    return {
        "query": query,
        "intent": intent,
        "entities": entities,
        "required_tools": required_tools,
    }
