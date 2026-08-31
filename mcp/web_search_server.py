"""
MCP Server: Web Search
Tools:
  - web_search(query) -> list of {title, snippet, url, source}

Uses Tavily/Serper if an API key is configured (see .env), otherwise
falls back to a curated trusted-medical-source mock so the whole
pipeline is runnable offline / without keys.
"""
import requests
from config import settings
from infrastructure.logger import error_logger

TRUSTED_SOURCES = ["who.int", "cdc.gov", "nih.gov", "mayoclinic.org", "medlineplus.gov"]

TOOL_SCHEMA = {
    "name": "web_search",
    "description": "Search the web and return snippets from trusted health sources.",
    "parameters": {"query": "string"},
}


def _mock_search(query: str):
    return [
        {
            "title": f"General health guidance related to: {query}",
            "snippet": (
                f"Public health guidance on '{query}' generally recommends consulting a "
                "licensed clinician for diagnosis, and following evidence-based guidelines "
                "published by recognized health authorities."
            ),
            "url": "https://www.who.int/",
            "source": "who.int (mock/offline mode)",
        },
        {
            "title": f"Patient information overview: {query}",
            "snippet": (
                f"Overview information about '{query}', including common symptoms, when to "
                "seek care, and general self-care guidance for mild cases."
            ),
            "url": "https://medlineplus.gov/",
            "source": "medlineplus.gov (mock/offline mode)",
        },
    ]


def call(query: str, max_results: int = 3):
    if settings.TAVILY_API_KEY:
        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                json={"api_key": settings.TAVILY_API_KEY, "query": query, "max_results": max_results},
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "title": r.get("title", ""),
                    "snippet": r.get("content", "")[:500],
                    "url": r.get("url", ""),
                    "source": r.get("url", "").split("/")[2] if r.get("url") else "web",
                }
                for r in data.get("results", [])[:max_results]
            ]
        except Exception as e:  # noqa: BLE001
            error_logger.error(f"Tavily search failed, falling back to mock: {e}")

    if settings.SERPER_API_KEY:
        try:
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": settings.SERPER_API_KEY},
                json={"q": query},
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", ""),
                    "url": r.get("link", ""),
                    "source": r.get("link", "").split("/")[2] if r.get("link") else "web",
                }
                for r in data.get("organic", [])[:max_results]
            ]
        except Exception as e:  # noqa: BLE001
            error_logger.error(f"Serper search failed, falling back to mock: {e}")

    return _mock_search(query)[:max_results]
