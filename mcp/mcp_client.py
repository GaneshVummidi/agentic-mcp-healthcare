"""
MCP Client
  - Connect to MCP Servers
  - List available tools
  - Call tools with arguments
  - Return results

For this reference implementation the "servers" are in-process Python
modules exposing a uniform call() interface (Web Search, Medical API,
Database). This mirrors the architecture 1:1 while keeping the whole
system runnable with a single `uvicorn` process. Swap any of them for
a real out-of-process MCP server (stdio/SSE) without touching agents
that depend on MCPClient.
"""
import time
from mcp import web_search_server, medical_api_server, database_server, document_store_server
from infrastructure.logger import system_logger

REGISTERED_SERVERS = {
    "web_search": web_search_server,
    "medical_api": medical_api_server,
    "database": database_server,
    "document_store": document_store_server,
}


class MCPClient:
    def list_tools(self):
        return {name: getattr(mod, "TOOL_SCHEMA", {}) for name, mod in REGISTERED_SERVERS.items() if name != "database"}

    def call_tool(self, server: str, **kwargs):
        module = REGISTERED_SERVERS.get(server)
        if module is None:
            raise ValueError(f"Unknown MCP server: {server}")
        start = time.time()
        result = module.call(**kwargs)
        elapsed_ms = round((time.time() - start) * 1000, 2)
        system_logger.info(f"MCP call server={server} args={kwargs} elapsed_ms={elapsed_ms}")
        return {"server": server, "result": result, "elapsed_ms": elapsed_ms}

    def call_tools_parallel(self, calls: list[dict]):
        """
        calls: [{"server": "web_search", "query": "..."}]
        Executes concurrently via a thread pool (tool calls are I/O bound),
        tagging each result with its originating call for traceability.
        """
        import concurrent.futures

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self.call_tool, **c): c for c in calls
            }
            for fut in concurrent.futures.as_completed(futures):
                origin = futures[fut]
                try:
                    res = fut.result()
                    res["origin"] = origin
                    results.append(res)
                except Exception as e:  # noqa: BLE001
                    results.append({"server": origin.get("server"), "error": str(e), "origin": origin})
        return results


mcp_client = MCPClient()
