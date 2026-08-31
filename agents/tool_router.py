"""
Agent 3: MCP Tool Router
  - Select appropriate tools
  - Plan tool execution
  - Parallel / Sequential execution (delegates parallel calls to MCPClient)
"""
from mcp.mcp_client import mcp_client


def plan_execution(query: str, session_id: str, required_tools: list[str]) -> list[dict]:
    """
    Translate the abstract tool names from the Query Agent into concrete
    MCP tool calls (server + arguments).
    """
    calls = []
    for tool in required_tools:
        if tool == "database":
            calls.append({"server": "database", "action": "cache_lookup", "query": query})
            calls.append({"server": "database", "action": "conversation_history", "session_id": session_id})
        elif tool == "web_search":
            calls.append({"server": "web_search", "query": query})
        elif tool.startswith("medical_api:"):
            kind = tool.split(":")[1]
            calls.append({"server": "medical_api", "query": query, "kind": kind})

    # Always check institution-uploaded documents (RAG). This is cheap when
    # no documents have been ingested (returns an empty list) and doesn't
    # require the Query Agent to know documents exist ahead of time.
    calls.append({"server": "document_store", "query": query, "top_k": 3})
    return calls


def execute(query: str, session_id: str, required_tools: list[str]) -> list[dict]:
    calls = plan_execution(query, session_id, required_tools)
    # Cache-lookup / history calls are cheap and sequential; web/medical calls
    # run in parallel via the MCP client's thread pool.
    sequential = [c for c in calls if c["server"] == "database"]
    parallel = [c for c in calls if c["server"] != "database"]

    results = [mcp_client.call_tool(**c) for c in sequential]
    if parallel:
        results.extend(mcp_client.call_tools_parallel(parallel))
    return results
