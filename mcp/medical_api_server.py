"""
MCP Server: Medical API
Tools:
  - drug_info(name) -> label/warnings info (openFDA, keyless public API)
  - disease_info(name) -> local curated dataset (guideline-style summaries)

This is intentionally conservative: it returns general reference info,
not diagnosis or dosing instructions, and always carries a disclaimer.
"""
import requests
from config import settings
from infrastructure.logger import error_logger

TOOL_SCHEMA = {
    "name": "medical_lookup",
    "description": "Look up general disease or drug reference information.",
    "parameters": {"query": "string", "kind": "disease|drug"},
}

# Small local guideline-style dataset used as an offline fallback / demo dataset.
DISEASE_DB = {
    "flu": {
        "summary": (
            "Influenza is a contagious respiratory illness caused by influenza viruses. "
            "Common symptoms include fever, cough, sore throat, body aches, and fatigue."
        ),
        "when_to_seek_care": "Difficulty breathing, chest pain, persistent high fever, or symptoms that worsen after improving.",
        "source": "CDC Influenza Overview",
    },
    "hypertension": {
        "summary": (
            "Hypertension (high blood pressure) is a chronic condition where blood pressure "
            "in the arteries is persistently elevated, increasing risk of heart disease and stroke."
        ),
        "when_to_seek_care": "Blood pressure readings consistently above 180/120, or symptoms like severe headache, chest pain, or vision changes.",
        "source": "WHO Hypertension Fact Sheet",
    },
    "diabetes": {
        "summary": (
            "Diabetes is a chronic condition affecting how the body turns food into energy, "
            "characterized by elevated blood glucose levels."
        ),
        "when_to_seek_care": "Symptoms of very high or very low blood sugar, or signs of diabetic ketoacidosis.",
        "source": "NIH Diabetes Overview",
    },
}


def disease_info(name: str):
    key = name.strip().lower()
    for k, v in DISEASE_DB.items():
        if k in key or key in k:
            return {"found": True, **v}
    return {
        "found": False,
        "summary": f"No curated local entry for '{name}'. Recommend deferring to verified web sources.",
        "when_to_seek_care": "Consult a licensed healthcare provider for personalized guidance.",
        "source": "local_dataset",
    }


def drug_info(name: str):
    if not settings.USE_OPENFDA:
        return {"found": False, "summary": "openFDA lookups disabled in config.", "source": "config"}
    try:
        resp = requests.get(
            "https://api.fda.gov/drug/label.json",
            params={"search": f'openfda.brand_name:"{name}"', "limit": 1},
            timeout=8,
        )
        if resp.status_code != 200:
            return {"found": False, "summary": f"No openFDA record found for '{name}'.", "source": "openfda"}
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return {"found": False, "summary": f"No openFDA record found for '{name}'.", "source": "openfda"}
        r = results[0]
        purpose = " ".join(r.get("purpose", []))[:400]
        warnings = " ".join(r.get("warnings", []))[:400]
        return {
            "found": True,
            "summary": purpose or "Purpose information not available.",
            "warnings": warnings or "Warnings information not available.",
            "source": "openFDA drug label database",
        }
    except Exception as e:  # noqa: BLE001
        error_logger.error(f"openFDA lookup failed: {e}")
        return {"found": False, "summary": f"Lookup failed for '{name}'.", "source": "openfda_error"}


def call(query: str, kind: str = "disease"):
    if kind == "drug":
        return drug_info(query)
    return disease_info(query)
