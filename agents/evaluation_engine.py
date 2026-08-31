"""
Agent 9: Evaluation Engine
  - Faithfulness
  - Relevance
  - Context Relevance
  - Hallucination Detection
  - Latency
  - Overall Score

Uses lightweight lexical-overlap heuristics (no extra model calls needed),
so evaluation is fast and works even fully offline. Swap in an
embedding-based or LLM-judge scorer later without changing the interface.
"""
import re
import time

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "of", "to", "in", "on", "for",
    "and", "or", "with", "this", "that", "it", "as", "be", "by", "at", "from",
}


def _tokenize(text: str) -> set:
    words = re.findall(r"[a-zA-Z]{3,}", (text or "").lower())
    return {w for w in words if w not in STOPWORDS}


def _overlap_score(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    intersection = len(ta & tb)
    return round(intersection / max(1, len(ta)), 3)


def evaluate(query: str, answer: str, verified_context: str, confidence: float, latency_ms: float) -> dict:
    faithfulness = min(1.0, round(_overlap_score(answer, verified_context) * 1.6, 3)) if verified_context else 0.3
    relevance = min(1.0, round(_overlap_score(answer, query) * 2.2, 3))
    context_relevance = min(1.0, round(_overlap_score(verified_context, query) * 2.0, 3)) if verified_context else 0.2

    # Hallucination risk approximated as inverse of faithfulness, nudged by source confidence.
    hallucination_risk = round(max(0.0, min(1.0, (1 - faithfulness) * (1 - 0.3 * confidence))), 3)

    overall_score = round(
        (0.35 * faithfulness + 0.25 * relevance + 0.20 * context_relevance +
         0.20 * (1 - hallucination_risk)),
        3,
    )

    return {
        "faithfulness": faithfulness,
        "relevance": relevance,
        "context_relevance": context_relevance,
        "hallucination_risk": hallucination_risk,
        "latency_ms": round(latency_ms, 1),
        "overall_score": overall_score,
    }


class Timer:
    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.time() - self._start) * 1000
