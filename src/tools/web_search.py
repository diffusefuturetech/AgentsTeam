"""Web search tool using ddgs (DuckDuckGo search) package."""

import json
import logging

from src.tools.base import ToolDefinition

logger = logging.getLogger(__name__)


async def _handle_web_search(args: dict) -> str:
    """Execute a web search and return top results."""
    query = args.get("query", "")
    max_results = args.get("max_results", 5)

    if not query:
        return "Error: 'query' parameter is required."

    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

        if not results:
            return f"No results found for: {query}"

        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"{i}. **{r.get('title', 'No title')}**\n"
                f"   URL: {r.get('href', 'N/A')}\n"
                f"   {r.get('body', 'No description')}"
            )
        return "\n\n".join(formatted)

    except ImportError:
        return "Error: ddgs package not installed. Run: pip install ddgs"
    except Exception as e:
        logger.warning(f"Web search failed for '{query}': {e}")
        return f"Search failed: {e}"


web_search_tool = ToolDefinition(
    name="web_search",
    description="Search the web for information using DuckDuckGo. Returns top results with titles, URLs, and descriptions.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
    handler=_handle_web_search,
)
