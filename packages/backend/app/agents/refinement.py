from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

from .base import BaseAgent
from .prompts import get_refinement_prompt
from ..llm.tool_handlers import (
    DEFAULT_ALLOWED_EXTENSIONS,
    MAX_WRITE_BYTES,
    build_filesystem_read_handler,
)
from ..llm.tools import ToolResult, get_filesystem_tools
from ..services.filesystem import FilesystemService

logger = logging.getLogger(__name__)


@dataclass
class RefinementResult:
    html: str
    preview_url: str
    filepath: str
    token_usage: Optional[dict] = None


class RefinementAgent(BaseAgent):
    agent_type = "refinement"

    def __init__(self, db, session_id: str, settings, event_emitter=None, agent_id=None, task_id=None) -> None:
        super().__init__(db, session_id, settings, event_emitter=event_emitter, agent_id=agent_id, task_id=task_id)
        self.system_prompt = get_refinement_prompt()

    async def refine(
        self,
        *,
        user_input: str,
        current_html: str,
        output_dir: str,
        history: Optional[list] = None,
    ) -> RefinementResult:
        history = history or []
        html = ""
        token_usage: Optional[dict] = None
        try:
            messages = self._build_messages(
                user_input=user_input,
                current_html=current_html,
                history=history,
            )
            tools = get_filesystem_tools()
            tool_handlers = {
                "filesystem_write": self._write_file_handler(output_dir),
                "filesystem_read": build_filesystem_read_handler(output_dir),
            }
            self._emit_agent_progress(message="Analyzing changes...", progress=30)
            response = await self._call_llm_with_tools(
                messages=messages,
                tools=tools,
                tool_handlers=tool_handlers,
                model=self.settings.model,
                temperature=self.settings.temperature,
            )
            html = self._extract_html(response.content)
            if not html:
                raise ValueError("No HTML detected in model response")
            if response.token_usage:
                token_usage = {
                    "input_tokens": response.token_usage.input_tokens,
                    "output_tokens": response.token_usage.output_tokens,
                    "total_tokens": response.token_usage.total_tokens,
                    "cost_usd": response.token_usage.cost_usd,
                }
        except Exception:
            logger.exception("RefinementAgent failed to use LLM, falling back to template")
            html = self._fallback_html(user_input=user_input, current_html=current_html)

        self._emit_agent_progress(message="Saving updates...", progress=80)
        path, preview_url = self._save_html(html=html, output_dir=output_dir)
        self._emit_agent_progress(message="Refinement complete", progress=100)
        return RefinementResult(
            html=html,
            preview_url=preview_url,
            filepath=str(path),
            token_usage=token_usage,
        )

    def _build_messages(
        self,
        *,
        user_input: str,
        current_html: str,
        history: Sequence[dict],
    ) -> list[dict]:
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
        ]
        for item in history:
            role = item.get("role", "user")
            content = item.get("content", "")
            if content:
                messages.append({"role": role, "content": content})

        instructions = user_input.strip() or "Refine the HTML based on feedback."
        html_text = current_html or ""
        content = (
            f"Current HTML:\n{html_text}\n\nUser modification request:\n{instructions}"
        )
        messages.append({"role": "user", "content": content})
        return messages

    def _extract_html(self, content: str) -> str:
        if not content:
            return ""

        marker_match = re.search(r"<HTML_OUTPUT>(.*?)</HTML_OUTPUT>", content, re.DOTALL | re.IGNORECASE)
        if marker_match:
            return marker_match.group(1).strip()

        lowered = content.lower()
        start = lowered.find("<!doctype html")
        end = lowered.rfind("</html>")
        if start != -1 and end != -1 and end > start:
            return content[start : end + len("</html>")].strip()

        html_match = re.search(r"<html\b[\s\S]*?</html>", content, re.IGNORECASE)
        if html_match:
            return html_match.group(0).strip()

        return ""

    def _save_html(self, *, html: str, output_dir: str) -> tuple[Path, str]:
        fs = FilesystemService(output_dir)
        index_path = fs.save_html(self.session_id, html, filename="index.html")
        timestamp = self._timestamp()
        version_name = f"v{timestamp}_refinement.html"
        fs.save_html(self.session_id, html, filename=version_name)
        absolute_path = Path(index_path).absolute()
        preview_url = absolute_path.as_uri()
        return absolute_path, preview_url

    @staticmethod
    def _ensure_base_dir(base_dir: Path) -> Path:
        resolved = base_dir.resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    @staticmethod
    def _validate_encoding(encoding: str) -> str:
        normalized = (encoding or "").lower()
        if normalized not in {"utf-8", "gbk"}:
            raise ValueError("Unsupported encoding")
        return normalized

    @staticmethod
    def _resolve_safe_path(
        base_dir: Path,
        path: str,
        *,
        allowed_extensions: Iterable[str],
    ) -> Path:
        if not path or not str(path).strip():
            raise ValueError("Path is required")

        base_dir = RefinementAgent._ensure_base_dir(base_dir)
        raw_path = Path(path)
        if raw_path.is_absolute():
            candidate = raw_path.resolve()
        else:
            candidate = (base_dir / raw_path).resolve()

        try:
            candidate.relative_to(base_dir)
        except ValueError as exc:
            raise ValueError("Path is outside of the allowed directory") from exc

        allowed = {ext.lower() for ext in allowed_extensions}
        if candidate.suffix.lower() not in allowed:
            raise ValueError("Unsupported file extension")

        return candidate

    def _write_file_handler(self, output_dir: str):
        base_dir = (Path(output_dir) / self.session_id).resolve()

        async def handler(path: str, content: str, encoding: str = "utf-8") -> ToolResult:
            resolved_encoding = self._validate_encoding(encoding)
            written_bytes = len(content.encode(resolved_encoding))
            if written_bytes > MAX_WRITE_BYTES:
                raise ValueError("Content exceeds maximum allowed size")
            target = self._resolve_safe_path(
                base_dir,
                path,
                allowed_extensions=DEFAULT_ALLOWED_EXTENSIONS,
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding=resolved_encoding)

            timestamp = self._timestamp()
            version_path = target.with_name(f"v{timestamp}_{target.name}")
            version_path.write_text(content, encoding=resolved_encoding)

            output = {
                "path": str(target),
                "version_path": str(version_path),
                "written_bytes": written_bytes,
                "version": timestamp,
            }

            if target.suffix.lower() == ".html" and target.name != "index.html":
                index_path = target.with_name("index.html")
                index_path.write_text(content, encoding=resolved_encoding)
                output["index_path"] = str(index_path)

            return ToolResult(success=True, output=output)

        return handler

    @staticmethod
    def _timestamp() -> int:
        return int(time.time() * 1000)

    def _fallback_html(self, *, user_input: str, current_html: str) -> str:
        if current_html:
            return current_html.replace("</body>", f"<p>{user_input}</p></body>")
        return ""


__all__ = ["RefinementAgent", "RefinementResult"]
