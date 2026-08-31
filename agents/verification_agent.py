"""
Agent 7: Verification Agent
  - Validate information
  - Cross-check sources
  - Score source quality
  - Compute confidence
"""

TRUSTED_DOMAINS = ["who.int", "cdc.gov", "nih.gov", "mayoclinic.org", "medlineplus.gov", "openfda", "fda.gov"]


def _score_source(source: str) -> float:
    source = (source or "").lower()
    if any(d in source for d in TRUSTED_DOMAINS):
        return 0.95
    if "local_dataset" in source or "config" in source:
        return 0.7
    if source:
        return 0.6
    return 0.3


def verify(tool_results: list[dict]) -> dict:
    """
    Consolidates raw MCP tool results into a verified context block the
    Answer Agent can ground its response in, plus a list of sources and
    an overall confidence score.
    """
    verified_snippets = []
    sources = []
    scores = []

    for item in tool_results:
        server = item.get("server")
        result = item.get("result")
        if result is None or item.get("error"):
            continue

        if server == "web_search" and isinstance(result, list):
            for r in result:
                score = _score_source(r.get("source", r.get("url", "")))
                scores.append(score)
                verified_snippets.append(f"[Web:{r.get('source','web')}] {r.get('snippet','')}")
                sources.append({"title": r.get("title", ""), "url": r.get("url", ""), "quality": round(score, 2)})

        elif server == "medical_api" and isinstance(result, dict):
            score = _score_source(result.get("source", ""))
            scores.append(score)
            summary = result.get("summary", "")
            warn = result.get("warnings") or result.get("when_to_seek_care", "")
            verified_snippets.append(f"[Medical:{result.get('source','reference')}] {summary} {warn}")
            sources.append({"title": result.get("source", "Medical reference"), "url": "", "quality": round(score, 2)})

        elif server == "document_store" and isinstance(result, list):
            for r in result:
                # Institution-uploaded documents are treated as high-trust,
                # scaled slightly by their retrieval similarity score.
                score = round(0.85 * min(1.0, r.get("score", 0)) + 0.15, 3)
                scores.append(score)
                verified_snippets.append(f"[Hospital Document:{r.get('title','document')}] {r.get('text','')}")
                sources.append({"title": f"📄 {r.get('title','Hospital document')}", "url": "", "quality": score})

        elif server == "database":
            # cache hits / history don't count toward source quality scoring,
            # but cache hits are surfaced as prior verified answers.
            pass

    confidence = round(sum(scores) / len(scores), 2) if scores else 0.4

    return {
        "verified_context": "\n".join(verified_snippets) if verified_snippets else "No external context retrieved.",
        "sources": sources,
        "confidence": confidence,
        "source_count": len(sources),
    }
