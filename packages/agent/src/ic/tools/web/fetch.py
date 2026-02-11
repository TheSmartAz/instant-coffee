"""WebFetch tool - fetch and analyze web content."""

from __future__ import annotations

import re
from typing import Any

import httpx

from ic.tools.base import (
    BaseTool,
    ToolParam,
    ToolResult,
    ToolCompleteEvent,
    ToolProgressEvent,
)


class WebFetch(BaseTool):
    """Fetch a web page and extract its main content."""

    name = "web_fetch"
    timeout_seconds = 30.0
    max_retries = 2
    description = (
        "Fetch a web page and extract its readable content. "
        "Use for reading documentation, blog posts, or articles. "
        "Returns the main content with basic HTML stripped."
    )
    parameters = [
        ToolParam(
            name="url",
            description="The URL to fetch (must start with http:// or https://)",
        ),
        ToolParam(
            name="max_length",
            type="integer",
            description="Maximum characters to return (default 10000)",
            required=False,
        ),
    ]

    def __init__(self, timeout: float = 30.0):
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
        url = kwargs.get("url", "")
        max_length = int(kwargs.get("max_length", 10000))

        if not url:
            yield ToolCompleteEvent(output="Error: url is required")
            return

        # Validate URL
        if not url.startswith(("http://", "https://")):
            yield ToolCompleteEvent(output="Error: URL must start with http:// or https://")
            return

        await self._emit_progress(f"Fetching: {url[:60]}...", 20)

        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                )
                response.raise_for_status()

                await self._emit_progress("Extracting content...", 60)

                # Extract and clean content
                content = self._extract_main_content(response.text, max_length)

                await self._emit_progress("Done.", 100)
                yield ToolCompleteEvent(
                    output=f"Content from {url}:\n\n{content}"
                )

        except httpx.HTTPStatusError as e:
            yield ToolCompleteEvent(output=f"HTTP error {e.response.status_code}: {url}")
        except httpx.TimeoutException:
            yield ToolCompleteEvent(output=f"Timeout fetching: {url}")
        except Exception as e:
            yield ToolCompleteEvent(output=f"Error fetching {url}: {e}")

    def _extract_main_content(self, html: str, max_length: int) -> str:
        """Extract readable content from HTML."""
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Remove common boilerplate elements
        html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<header[^>]*>.*?</header>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<aside[^>]*>.*?</aside>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Extract text from common content tags
        content_patterns = [
            r'<article[^>]*>(.*?)</article>',
            r'<main[^>]*>(.*?)</main>',
            r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
            r'<h1[^>]*>(.*?)</h1>',
            r'<h2[^>]*>(.*?)</h2>',
            r'<p[^>]*>(.*?)</p>',
            r'<li[^>]*>(.*?)</li>',
        ]

        extracted_parts = []

        for pattern in content_patterns:
            matches = re.findall(pattern, html, flags=re.DOTALL | re.IGNORECASE)
            for match in matches:
                # Remove HTML tags
                text = re.sub(r'<[^>]+>', ' ', match)
                # Decode HTML entities
                text = re.sub(r'&nbsp;', ' ', text)
                text = re.sub(r'&amp;', '&', text)
                text = re.sub(r'&lt;', '<', text)
                text = re.sub(r'&gt;', '>', text)
                text = re.sub(r'&quot;', '"', text)
                text = re.sub(r'&#39;', "'", text)
                # Clean whitespace
                text = re.sub(r'\s+', ' ', text).strip()
                if text and len(text) > 20:  # Only meaningful content
                    extracted_parts.append(text)

        if not extracted_parts:
            # Fallback: extract all text
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text).strip()
            extracted_parts = [text]

        # Join and truncate
        content = " ".join(extracted_parts)
        content = re.sub(r'\s+', ' ', content).strip()

        if len(content) > max_length:
            content = content[:max_length] + "...[truncated]"

        return content
