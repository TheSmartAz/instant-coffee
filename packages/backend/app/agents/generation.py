from __future__ import annotations

import html as html_lib
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence

from .base import BaseAgent
from .prompts import get_generation_prompt
from ..llm.tool_handlers import MAX_WRITE_BYTES
from ..llm.tools import get_filesystem_tools
from ..services.filesystem import FilesystemService

logger = logging.getLogger(__name__)

ALLOWED_ENCODINGS = {"utf-8", "gbk"}
ALLOWED_WRITE_EXTENSIONS = {".html"}


@dataclass
class GenerationProgress:
    message: str
    progress: int


@dataclass
class GenerationResult:
    html: str
    preview_url: str
    filepath: str
    token_usage: Optional[dict] = None


class GenerationAgent(BaseAgent):
    agent_type = "generation"

    def __init__(self, db, session_id: str, settings, event_emitter=None, agent_id=None, task_id=None) -> None:
        super().__init__(db, session_id, settings, event_emitter=event_emitter, agent_id=agent_id, task_id=task_id)
        self.system_prompt = get_generation_prompt()
        self._current_html: Optional[str] = None

    def progress_steps(self) -> List[GenerationProgress]:
        return [
            GenerationProgress(message="Analyzing requirements", progress=20),
            GenerationProgress(message="Generating layout", progress=60),
            GenerationProgress(message="Finalizing output", progress=90),
        ]

    async def generate(
        self,
        *,
        requirements: str,
        output_dir: str,
        history: Sequence[dict] | None = None,
        current_html: Optional[str] = None,
        stream: bool = True,
    ) -> GenerationResult:
        history = history or []
        html = ""
        response = None
        resolved_current_html = current_html if current_html is not None else self._current_html

        try:
            messages = self._build_messages(
                requirements=requirements,
                history=history,
                current_html=resolved_current_html,
            )
            if stream:
                response = await self._call_llm(
                    messages=messages,
                    agent_type=self.agent_type,
                    model=self.settings.model,
                    temperature=self.settings.temperature,
                    stream=True,
                    context="generation",
                )
            else:
                tools = get_filesystem_tools()
                tool_handlers = {"filesystem_write": self._write_file_handler(output_dir)}
                response = await self._call_llm_with_tools(
                    messages=messages,
                    tools=tools,
                    tool_handlers=tool_handlers,
                    model=self.settings.model,
                    temperature=self.settings.temperature,
                    context="generation",
                )
            html = self._extract_html(response.content)
            if not html and stream:
                logger.warning("GenerationAgent retrying without streaming for HTML extraction")
                response = await self._call_llm(
                    messages=messages,
                    agent_type=self.agent_type,
                    model=self.settings.model,
                    temperature=self.settings.temperature,
                    stream=False,
                    emit_progress=False,
                    context="generation-retry",
                )
                html = self._extract_html(response.content)
            if not html:
                raise ValueError("No HTML detected in model response")
        except Exception:
            logger.exception("GenerationAgent failed to use LLM, falling back to template")
            html = self._fallback_html(requirements)

        filepath, preview_url = self._save_html(output_dir=output_dir, html=html)
        self._current_html = html
        token_usage = self._serialize_token_usage(response)
        return GenerationResult(
            html=html,
            preview_url=preview_url,
            filepath=filepath,
            token_usage=token_usage,
        )

    def _build_messages(
        self,
        *,
        requirements: str,
        history: Sequence[dict],
        current_html: Optional[str],
    ) -> list[dict]:
        resolved_current_html = current_html if current_html is not None else self._current_html
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
        ]
        for item in history:
            role = item.get("role", "user")
            content = item.get("content", "")
            if content:
                messages.append({"role": role, "content": content})

        requirements_text = requirements.strip() or "Generate a mobile-first HTML page."
        user_parts = [f"Requirements:\n{requirements_text}"]
        if resolved_current_html:
            user_parts.append(f"Current HTML:\n{resolved_current_html}")
        messages.append({"role": "user", "content": "\n\n".join(user_parts)})
        return messages

    def _extract_html(self, content: str) -> str:
        if not content:
            return ""
        candidate = content.strip()
        if not candidate:
            return ""

        candidate = html_lib.unescape(candidate)

        fence_match = re.search(r"```(?:html)?\s*(.*?)```", candidate, re.DOTALL | re.IGNORECASE)
        if fence_match:
            candidate = fence_match.group(1).strip()

        marker_match = re.search(r"<HTML_OUTPUT>(.*?)</HTML_OUTPUT>", candidate, re.DOTALL | re.IGNORECASE)
        if marker_match:
            return marker_match.group(1).strip()
        marker_start = re.search(r"<HTML_OUTPUT>", candidate, re.IGNORECASE)
        if marker_start:
            candidate = candidate[marker_start.end() :].strip()

        lowered = candidate.lower()
        start = lowered.find("<!doctype html")
        end = lowered.rfind("</html>")
        if start != -1:
            if end != -1 and end > start:
                return candidate[start : end + len("</html>")].strip()
            return candidate[start:].strip()

        html_match = re.search(r"<html\b[\s\S]*?</html>", candidate, re.IGNORECASE)
        if html_match:
            return html_match.group(0).strip()

        logger.warning("GenerationAgent failed to extract HTML from response")
        return ""

    def _save_html(self, *, output_dir: str, html: str) -> tuple[str, str]:
        fs = FilesystemService(output_dir)
        path = fs.save_html(self.session_id, html, filename="index.html")
        self._write_version_copy(path, html)
        preview_url = Path(path).absolute().as_uri()
        return str(Path(path).absolute()), preview_url

    def _write_version_copy(self, path: Path, html: str) -> Path:
        timestamp = self._timestamp()
        version_path = path.with_name(f"v{timestamp}_{path.name}")
        version_path.write_text(html, encoding="utf-8")
        return version_path

    def _write_file_handler(self, output_dir: str) -> Callable[..., Any]:
        session_dir = (Path(output_dir).resolve() / self.session_id).resolve()

        async def handler(path: str, content: str, encoding: str = "utf-8") -> dict:
            resolved_encoding = self._validate_encoding(encoding)
            written_bytes = len(content.encode(resolved_encoding))
            if written_bytes > MAX_WRITE_BYTES:
                raise ValueError("Content exceeds maximum allowed size")
            target = self._resolve_safe_path(session_dir=session_dir, path=path)
            session_dir.mkdir(parents=True, exist_ok=True)
            preview_path = session_dir / "index.html"
            preview_path.write_text(content, encoding=resolved_encoding)
            timestamp = self._timestamp()
            version_name = f"v{timestamp}_{target.name}"
            version_path = session_dir / version_name
            version_path.write_text(content, encoding=resolved_encoding)
            output = {
                "preview_path": str(preview_path),
                "version_path": str(version_path.name),
                "version": timestamp,
                "written_bytes": written_bytes,
            }
            return {
                "success": True,
                "preview_path": output["preview_path"],
                "version_path": output["version_path"],
                "version": output["version"],
                "output": output,
            }

        return handler

    def _resolve_safe_path(self, *, session_dir: Path, path: str) -> Path:
        if not path or not str(path).strip():
            raise ValueError("Path is required")
        candidate = Path(path)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (session_dir / candidate).resolve()
        session_resolved = session_dir.resolve()
        try:
            resolved.relative_to(session_resolved)
        except ValueError as exc:
            raise ValueError("Path is outside of the allowed directory") from exc
        if resolved.suffix.lower() not in ALLOWED_WRITE_EXTENSIONS:
            raise ValueError("Unsupported file extension")
        return resolved

    def _validate_encoding(self, encoding: str) -> str:
        normalized = (encoding or "").lower()
        if normalized not in ALLOWED_ENCODINGS:
            raise ValueError("Unsupported encoding")
        return normalized

    def _serialize_token_usage(self, response: Any) -> Optional[dict]:
        usage = getattr(response, "token_usage", None) if response is not None else None
        if usage is None:
            return None
        return {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
            "cost_usd": usage.cost_usd,
        }

    def _timestamp(self) -> int:
        return int(time.time() * 1000)

    def _fallback_html(self, requirements: str) -> str:
        safe_text = requirements.strip() or "Generated Page"
        return (
            "<!doctype html>\n"
            "<html><head><meta charset=\"utf-8\"/>"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>"
            "<title>Instant Coffee</title>"
            "<style>body{font-family:Arial,sans-serif;padding:24px;}h1{font-size:24px;}</style>"
            "</head><body>"
            f"<h1>Generated Page</h1><p>{safe_text}</p>"
            "</body></html>"
        )


__all__ = ["GenerationAgent", "GenerationProgress", "GenerationResult"]
