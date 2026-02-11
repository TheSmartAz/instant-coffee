"""AI-powered HTML to React + Tailwind converter.

Calls Claude to convert raw HTML pages into React TSX components,
extracting shared components and unifying design tokens.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)

FILE_SEPARATOR_PATTERN = re.compile(
    r"^---\s*FILE:\s*(.+?)\s*---\s*$", re.MULTILINE
)

MAX_HTML_CHARS = 100_000


@dataclass
class PageHtml:
    slug: str
    title: str
    html: str


@dataclass
class ConvertedFile:
    path: str       # e.g. "src/components/Nav.tsx"
    content: str    # tsx source code


SYSTEM_PROMPT = """\
You are a React + Tailwind CSS expert. Your task is to convert HTML pages \
into React components.

Rules:
1. Identify repeated UI structures across pages and extract them as shared \
components (e.g. Nav, Footer, Button).
2. All styling must use Tailwind utility classes. Do NOT use inline styles \
or <style> tags.
3. Extract colors, fonts, and spacing from the HTML into a unified \
tailwind.config.js with a custom theme.
4. Each shared component goes in its own file under src/components/.
5. Each page goes in its own file under src/pages/.
6. Use TypeScript, functional components, and named exports.
7. Mobile-first design: max-width 430px container, hidden scrollbar.
8. Preserve the visual design of the original HTML exactly.
9. Import React at the top of every file: import React from 'react'
10. Page components should use default exports.
11. Always generate a tailwind.config.js file.

Output format:
Use --- FILE: <path> --- as a separator before each file's content.
Do NOT wrap the output in markdown code fences.

Example output:
--- FILE: src/components/Nav.tsx ---
import React from 'react'

export function Nav() {
  return <nav className="...">...</nav>
}
--- FILE: src/pages/landing.tsx ---
import React from 'react'
import { Nav } from '../components/Nav'

export default function LandingPage() {
  return <div>...</div>
}
--- FILE: tailwind.config.js ---
module.exports = { ... }
"""


def _build_user_prompt(
    pages: list[PageHtml],
    product_doc_content: str | None = None,
) -> str:
    parts: list[str] = []

    if product_doc_content:
        parts.append("## Product Doc")
        parts.append(product_doc_content)
        parts.append("")

    parts.append("## HTML Pages")
    parts.append("")

    for page in pages:
        parts.append(f"### {page.slug} ({page.title})")
        parts.append("```html")
        parts.append(page.html)
        parts.append("```")
        parts.append("")

    parts.append(
        "Convert the above HTML pages into React + Tailwind components. "
        "Extract shared components and unify design tokens."
    )
    return "\n".join(parts)


def _truncate_styles(html: str) -> str:
    """Strip large <style> blocks to stay within token limits."""
    def _shorten(match: re.Match) -> str:
        content = match.group(1)
        if len(content) > 500:
            return f"<style>/* truncated – {len(content)} chars */</style>"
        return match.group(0)

    return re.sub(r"<style[^>]*>(.*?)</style>", _shorten, html, flags=re.DOTALL)


def _prepare_pages(pages: list[PageHtml]) -> list[PageHtml]:
    """Truncate HTML if total size exceeds limit."""
    total = sum(len(p.html) for p in pages)
    if total <= MAX_HTML_CHARS:
        return pages
    return [PageHtml(slug=p.slug, title=p.title, html=_truncate_styles(p.html)) for p in pages]


def parse_converted_files(text: str) -> list[ConvertedFile]:
    """Parse AI response into ConvertedFile list using file separators."""
    # Strip markdown code fences if the model wrapped the output
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
        cleaned = cleaned[first_newline + 1:]
    if cleaned.endswith("```"):
        cleaned = cleaned[: cleaned.rfind("```")]

    splits = FILE_SEPARATOR_PATTERN.split(cleaned)
    # splits[0] is text before first separator (usually empty)
    # then alternating: path, content, path, content, ...
    files: list[ConvertedFile] = []
    i = 1
    while i < len(splits) - 1:
        path = splits[i].strip()
        content = splits[i + 1].strip()
        if path and content:
            files.append(ConvertedFile(path=path, content=content))
        i += 2
    return files


class HtmlToReactConverter:
    """Converts HTML pages to React + Tailwind via Claude API."""

    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    MAX_RETRIES = 2
    BASE_DELAY = 2.0

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        api_version: str | None = None,
        model: str | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.anthropic_api_key
        self._base_url = base_url or settings.anthropic_base_url
        self._api_version = api_version or settings.anthropic_api_version
        self._model = model or self.DEFAULT_MODEL
        if not self._api_key:
            raise ValueError("Anthropic API key is required for HTML-to-React conversion")

    async def convert(
        self,
        pages: list[PageHtml],
        product_doc_content: str | None = None,
    ) -> list[ConvertedFile]:
        """Call Claude to convert HTML pages to React components."""
        if not pages:
            raise ValueError("At least one HTML page is required")

        prepared = _prepare_pages(pages)
        user_prompt = _build_user_prompt(prepared, product_doc_content)

        import asyncio

        last_error: Exception | None = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response_text = await self._call_api(user_prompt)
                files = parse_converted_files(response_text)
                if not files:
                    raise ValueError("AI returned no files in response")
                return files
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "HTML-to-React conversion attempt %d failed: %s",
                    attempt + 1,
                    exc,
                )
                if attempt < self.MAX_RETRIES:
                    delay = self.BASE_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)

        raise RuntimeError(
            f"HTML-to-React conversion failed after {self.MAX_RETRIES + 1} attempts: {last_error}"
        ) from last_error

    async def retry_with_errors(
        self,
        pages: list[PageHtml],
        previous_files: list[ConvertedFile],
        build_errors: str,
        product_doc_content: str | None = None,
    ) -> list[ConvertedFile]:
        """Retry conversion with build error feedback."""
        prepared = _prepare_pages(pages)
        base_prompt = _build_user_prompt(prepared, product_doc_content)

        error_prompt = (
            f"{base_prompt}\n\n"
            f"## Previous Build Errors\n"
            f"The previous conversion produced code that failed to compile. "
            f"Fix the following errors:\n\n"
            f"```\n{build_errors[:3000]}\n```\n\n"
            f"Generate all files again with the errors fixed."
        )

        response_text = await self._call_api(error_prompt)
        files = parse_converted_files(response_text)
        if not files:
            raise ValueError("AI returned no files in retry response")
        return files

    async def _call_api(self, user_prompt: str) -> str:
        """Make a single API call to Claude."""
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self._api_version,
            "content-type": "application/json",
        }
        payload = {
            "model": self._model,
            "max_tokens": 16000,
            "temperature": 0.2,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        timeout = httpx.Timeout(180.0, connect=30.0)
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=timeout
        ) as client:
            response = await client.post(
                "/v1/messages", json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()

        content_blocks = data.get("content", [])
        if not content_blocks:
            raise ValueError("Empty response from Claude API")

        return content_blocks[0].get("text", "")


__all__ = [
    "ConvertedFile",
    "HtmlToReactConverter",
    "PageHtml",
    "parse_converted_files",
]
