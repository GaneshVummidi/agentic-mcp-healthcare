"""
Agent 8: Answer Agent (LLM - Qwen 3B, served locally via Ollama)
  - Generate grounded answer
  - Use verified context
  - Follow medical safety rules
  - Add disclaimers
"""
import json
import requests
from config import settings
from infrastructure.logger import error_logger, system_logger

SYSTEM_PROMPT = """You are MediAegis AI, a careful medical-information assistant.
Rules:
1. Answer ONLY using the VERIFIED CONTEXT provided. If the context is insufficient, say so plainly.
2. Never provide a diagnosis, prescription, or exact dosage. Offer general, educational information only.
3. Always recommend consulting a licensed healthcare professional for personal medical decisions.
4. Be concise, clear, and empathetic. Avoid alarming language unless the situation is genuinely urgent.
5. If the user describes emergency symptoms, prioritize telling them to seek immediate care.
"""


def _build_prompt(query: str, verified_context: str, history: list[dict]) -> str:
    history_text = ""
    for turn in history[-4:]:
        role = "User" if turn["role"] == "user" else "Assistant"
        history_text += f"{role}: {turn['content']}\n"

    return f"""{SYSTEM_PROMPT}

CONVERSATION HISTORY:
{history_text if history_text else '(none)'}

VERIFIED CONTEXT (from web search, medical reference APIs, and cache):
{verified_context}

USER QUESTION:
{query}

Write a grounded, safe, well-organized answer. End with one short medical disclaimer sentence.
"""


def generate(query: str, verified_context: str, history: list[dict]) -> str:
    prompt = _build_prompt(query, verified_context, history)
    try:
        resp = requests.post(
            f"{settings.OLLAMA_HOST}/api/generate",
            json={"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
        answer = data.get("response", "").strip()
        if not answer:
            raise ValueError("Empty response from Ollama")
        return answer
    except Exception as e:  # noqa: BLE001
        error_logger.error(f"Ollama generation failed: {e}")
        system_logger.warning("Falling back to template answer (is Ollama running with the model pulled?).")
        return _fallback_answer(query, verified_context)


def generate_stream(query: str, verified_context: str, history: list[dict]):
    """
    Generator that yields answer text incrementally as Ollama streams tokens.
    Falls back to yielding the full fallback answer in one chunk if Ollama
    is unreachable, so the SSE endpoint always terminates cleanly.
    """
    prompt = _build_prompt(query, verified_context, history)
    try:
        with requests.post(
            f"{settings.OLLAMA_HOST}/api/generate",
            json={"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": True},
            timeout=90,
            stream=True,
        ) as resp:
            resp.raise_for_status()
            got_any = False
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                token = chunk.get("response", "")
                if token:
                    got_any = True
                    yield token
                if chunk.get("done"):
                    break
            if not got_any:
                raise ValueError("Empty stream from Ollama")
    except Exception as e:  # noqa: BLE001
        error_logger.error(f"Ollama streaming failed: {e}")
        system_logger.warning("Falling back to template answer for stream (is Ollama running with the model pulled?).")
        yield _fallback_answer(query, verified_context)


def _fallback_answer(query: str, verified_context: str) -> str:
    return (
        f"I couldn't reach the local Qwen model (Ollama), so here is the verified reference "
        f"information gathered for your question about \"{query}\":\n\n{verified_context}\n\n"
        "Please consult a licensed healthcare professional for personal medical advice. "
        "(To enable full AI-generated answers, make sure `ollama serve` is running and the "
        "configured model has been pulled — see the README.)"
    )
