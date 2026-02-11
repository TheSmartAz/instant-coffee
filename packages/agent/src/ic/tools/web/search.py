"""WebSearch tool - search the web for information."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from ic.tools.base import (
    BaseTool,
    ToolParam,
    ToolResult,
    ToolCompleteEvent,
    ToolProgressEvent,
)


class WebSearch(BaseTool):
    """Search the web using DuckDuckGo (no API key required)."""

    name = "web_search"
    timeout_seconds = 30.0
    max_retries = 2
    description = (
        "Search the web for current information. "
        "Use for finding recent documentation, news, or answers to specific questions. "
        "Returns a list of relevant web pages with titles, URLs, and snippets."
    )
    parameters = [
        ToolParam(
            name="query",
            description="Search query (2-5 keywords work best)",
        ),
        ToolParam(
            name="max_results",
            type="integer",
            description="Maximum number of results (default 10)",
            required=False,
        ),
    ]

    def __init__(self, timeout: float = 15.0):
        super().__init__()
        self._timeout = timeout

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute (simple interface)."""
        async for event in self.execute_stream(**kwargs):
            if isinstance(event, ToolCompleteEvent):
                return ToolResult(output=event.output)
        return ToolResult(output="")

    async def execute_stream(self, **kwargs):
        """Execute with streaming progress."""
        query = kwargs.get("query", "")
        max_results = int(kwargs.get("max_results", 10))

        if not query:
            yield ToolCompleteEvent(output="Error: query is required")
            return

        await self._emit_progress(f"Searching: {query[:50]}...", 20)

        try:
            results = await self._duckduckgo_search(query, max_results)

            await self._emit_progress(f"Found {len(results)} results", 80)

            if not results:
                yield ToolCompleteEvent(output=f"No results found for: {query}")
                return

            # Format results
            formatted = []
            for i, r in enumerate(results, 1):
                formatted.append(f"{i}. {r.get('title', 'Untitled')}")
                formatted.append(f"   URL: {r.get('url', '')}")
                if r.get("snippet"):
                    formatted.append(f"   {r['snippet'][:200]}")
                formatted.append("")

            await self._emit_progress("Done.", 100)
            yield ToolCompleteEvent(
                output=f"Search results for '{query}':\n\n" + "\n".join(formatted)
            )

        except Exception as e:
            yield ToolCompleteEvent(output=f"Search error: {e}")

    async def _duckduckgo_search(
        self, query: str, max_results: int = 10
    ) -> list[dict]:
        """Search using DuckDuckGo HTML version (no API key needed)."""
        url = "https://html.duckduckgo.com/html/"
        params = {
            "q": query,
            "kl": "wt-wt",  # No location filter
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url, params=params, headers=headers, follow_redirects=True)
            response.raise_for_status()

            # Parse HTML results
            from html.parser import HTMLParser

            class DuckDuckGoParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.results = []
                    self.in_result = False
                    self.in_title = False
                    self.in_snippet = False
                    self.current = {}

                def handle_starttag(self, tag, attrs):
                    attrs_dict = dict(attrs)
                    class_name = attrs_dict.get("class", "")

                    if tag == "div" and "result" in class_name:
                        self.in_result = True
                        self.current = {}

                    elif self.in_result:
                        if tag == "a" and "result__a" in class_name:
                            self.current["url"] = attrs_dict.get("href", "")
                            self.in_title = True

                        elif tag == "a" and class_name == "result__a":
                            self.in_snippet = True

                def handle_endtag(self, tag):
                    if tag == "div" and self.in_result:
                        if self.current.get("url"):
                            self.results.append(self.current)
                        self.in_result = False
                        self.current = {}
                    elif tag == "a":
                        self.in_title = False
                        self.in_snippet = False

                def handle_data(self, data):
                    if self.in_title:
                        self.current["title"] = self.current.get("title", "") + data
                    elif self.in_snippet:
                        self.current["snippet"] = self.current.get("snippet", "") + data

            parser = DuckDuckGoParser()
            parser.feed(response.text)

            return parser.results[:max_results]
