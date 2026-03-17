"""Web fetch tool — fetches URL content and strips HTML."""

import logging
import re

from src.tools.base import ToolDefinition

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 8000


def _strip_html(html: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def _handle_web_fetch(args: dict) -> str:
    """Fetch a URL and return its text content."""
    url = args.get("url", "")
    if not url:
        return "Error: 'url' parameter is required."

    try:
        import httpx

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            text = _strip_html(response.text)
        else:
            text = response.text

        if len(text) > MAX_CONTENT_LENGTH:
            text = text[:MAX_CONTENT_LENGTH] + "\n... (truncated)"

        return text

    except Exception as e:
        logger.warning(f"Web fetch failed for '{url}': {e}")
        return f"Fetch failed: {e}"


web_fetch_tool = ToolDefinition(
    name="web_fetch",
    description="Fetch the content of a web page URL. HTML is stripped to plain text and truncated to 8000 characters.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch",
            },
        },
        "required": ["url"],
    },
    handler=_handle_web_fetch,
)
