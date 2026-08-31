"""
AGENT ORCHESTRATOR

System Flow:
User Query -> Query Agent -> Safety Agent -> MCP Tool Router -> MCP Client
  -> Tools (Web / API / DB) -> Tool Results -> Verification Agent
  -> Qwen 3B (Answer Agent) -> Evaluation Engine -> Final Response
"""
import time
import uuid

from agents import query_agent, safety_agent, tool_router, verification_agent, answer_agent, evaluation_engine
from infrastructure import db, cache
from infrastructure.logger import system_logger, log_audit_event


def _run_pre_answer_pipeline(query: str, session_id: str, t0: float):
    """
    Shared steps 1-7 (Query -> Safety -> Tool Router -> MCP Client -> Verification)
    used by both the blocking and the streaming entrypoints.

    Returns a tuple:
      (short_circuit_response | None, query_analysis, safety, verification, cached)
    """
    db.save_message(session_id, "user", query)
    log_audit_event("query_received", session_id, {"query": query})

    # 1. Query Agent
    query_analysis = query_agent.analyze(query)
    system_logger.info(f"[QueryAgent] {query_analysis}")

    # 2. Safety Agent
    safety = safety_agent.assess(query)
    system_logger.info(f"[SafetyAgent] {safety}")

    if safety["is_blocked"] or safety["is_emergency"]:
        latency_ms = (time.time() - t0) * 1000
        final_answer = safety["guardrail_message"]
        db.save_message(session_id, "assistant", final_answer)
        log_audit_event("guardrail_triggered", session_id, {"risk_level": safety["risk_level"]})
        short_circuit = {
            "session_id": session_id,
            "answer": final_answer,
            "sources": [],
            "confidence": 1.0,
            "evaluation": {
                "faithfulness": 1.0, "relevance": 1.0, "context_relevance": 1.0,
                "hallucination_risk": 0.0, "latency_ms": round(latency_ms, 1), "overall_score": 1.0,
            },
            "disclaimers": ["This is an automated safety guardrail response, not a substitute for emergency services."],
            "risk_level": safety["risk_level"],
            "query_analysis": query_analysis,
        }
        return short_circuit, query_analysis, safety, None, None

    # Check cache first (Database MCP: cache_lookup)
    cached = cache.cache_get("qa", query.strip().lower())
    if cached:
        log_audit_event("cache_hit", session_id, {"query": query})
        cached = dict(cached)
        cached["session_id"] = session_id
        cached["from_cache"] = True
        db.save_message(session_id, "assistant", cached["answer"])
        return cached, query_analysis, safety, None, cached

    # 3. MCP Tool Router -> MCP Client -> Tools (Web / API / DB)
    tool_results = tool_router.execute(query, session_id, query_analysis["required_tools"])
    system_logger.info(f"[ToolRouter] executed {len(tool_results)} tool calls")

    # 7. Verification Agent
    verification = verification_agent.verify(tool_results)
    system_logger.info(f"[VerificationAgent] confidence={verification['confidence']} sources={verification['source_count']}")

    return None, query_analysis, safety, verification, None


def handle_query(query: str, session_id: str | None = None) -> dict:
    session_id = session_id or str(uuid.uuid4())
    t0 = time.time()

    short_circuit, query_analysis, safety, verification, cached = _run_pre_answer_pipeline(query, session_id, t0)
    if short_circuit is not None:
        return short_circuit

    # 8. Answer Agent (Qwen 3B via Ollama)
    history = db.get_history(session_id, limit=6)
    final_answer = answer_agent.generate(query, verification["verified_context"], history)

    latency_ms = (time.time() - t0) * 1000

    # 9. Evaluation Engine
    metrics = evaluation_engine.evaluate(
        query=query,
        answer=final_answer,
        verified_context=verification["verified_context"],
        confidence=verification["confidence"],
        latency_ms=latency_ms,
    )

    disclaimers = [
        "This response is for general educational purposes only and is not a medical diagnosis.",
        "Always consult a licensed healthcare professional for decisions about your health.",
    ]

    response = {
        "session_id": session_id,
        "answer": final_answer,
        "sources": verification["sources"],
        "confidence": verification["confidence"],
        "evaluation": metrics,
        "disclaimers": disclaimers,
        "risk_level": safety["risk_level"],
        "query_analysis": query_analysis,
        "from_cache": False,
    }

    db.save_message(session_id, "assistant", final_answer)
    db.save_evaluation(session_id, query, final_answer, metrics, latency_ms)
    cache.cache_set("qa", query.strip().lower(), response)
    log_audit_event("response_generated", session_id, {"overall_score": metrics["overall_score"]})

    return response


def handle_query_stream(query: str, session_id: str | None = None):
    """
    Generator used by the SSE endpoint. Yields dicts describing events:
      {"type": "meta", ...}      - sent once, right before token streaming starts
      {"type": "token", "text": "..."} - one per generated token/chunk
      {"type": "final", ...}     - full structured response, sent once at the end
      {"type": "short_circuit", ...} - safety guardrail or cache hit (no streaming needed)
    """
    session_id = session_id or str(uuid.uuid4())
    t0 = time.time()

    short_circuit, query_analysis, safety, verification, cached = _run_pre_answer_pipeline(query, session_id, t0)
    if short_circuit is not None:
        yield {"type": "short_circuit", "data": short_circuit}
        return

    yield {
        "type": "meta",
        "data": {
            "session_id": session_id,
            "sources": verification["sources"],
            "confidence": verification["confidence"],
            "risk_level": safety["risk_level"],
        },
    }

    history = db.get_history(session_id, limit=6)
    full_answer = ""
    for token in answer_agent.generate_stream(query, verification["verified_context"], history):
        full_answer += token
        yield {"type": "token", "data": {"text": token}}

    latency_ms = (time.time() - t0) * 1000
    metrics = evaluation_engine.evaluate(
        query=query,
        answer=full_answer,
        verified_context=verification["verified_context"],
        confidence=verification["confidence"],
        latency_ms=latency_ms,
    )
    disclaimers = [
        "This response is for general educational purposes only and is not a medical diagnosis.",
        "Always consult a licensed healthcare professional for decisions about your health.",
    ]

    final_response = {
        "session_id": session_id,
        "answer": full_answer,
        "sources": verification["sources"],
        "confidence": verification["confidence"],
        "evaluation": metrics,
        "disclaimers": disclaimers,
        "risk_level": safety["risk_level"],
        "query_analysis": query_analysis,
        "from_cache": False,
    }

    db.save_message(session_id, "assistant", full_answer)
    db.save_evaluation(session_id, query, full_answer, metrics, latency_ms)
    cache.cache_set("qa", query.strip().lower(), final_response)
    log_audit_event("response_generated_stream", session_id, {"overall_score": metrics["overall_score"]})

    yield {"type": "final", "data": final_response}
