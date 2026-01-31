from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from .tools import ToolResult
from ..generators.mobile_html import validate_mobile_html

ALLOWED_ENCODINGS = {"utf-8", "gbk"}
DEFAULT_ALLOWED_EXTENSIONS = {".html", ".css", ".js"}
MAX_WRITE_BYTES = 1_000_000


def _validate_encoding(encoding: str) -> str:
    normalized = (encoding or "").lower()
    if normalized not in ALLOWED_ENCODINGS:
        raise ValueError("Unsupported encoding")
    return normalized


def _validate_content_size(content: str, encoding: str) -> int:
    size = len(content.encode(encoding))
    if size > MAX_WRITE_BYTES:
        raise ValueError("Content exceeds maximum allowed size")
    return size


def _ensure_base_dir(base_dir: Path) -> Path:
    resolved = base_dir.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _resolve_safe_path(
    base_dir: Path,
    path: str,
    *,
    allowed_extensions: Iterable[str],
) -> Path:
    if not path or not str(path).strip():
        raise ValueError("Path is required")

    base_dir = _ensure_base_dir(base_dir)
    raw_path = Path(path)
    if raw_path.is_absolute():
        candidate = raw_path.resolve()
    else:
        candidate = (base_dir / raw_path).resolve()

    try:
        candidate.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError("Path is outside of the allowed directory") from exc

    if candidate.suffix.lower() not in {ext.lower() for ext in allowed_extensions}:
        raise ValueError("Unsupported file extension")

    return candidate


def build_filesystem_write_handler(
    output_dir: str,
    *,
    allowed_extensions: Iterable[str] = DEFAULT_ALLOWED_EXTENSIONS,
) -> Callable[..., Any]:
    base_dir = Path(output_dir)

    async def handler(path: str, content: str, encoding: str = "utf-8") -> ToolResult:
        resolved_encoding = _validate_encoding(encoding)
        written_bytes = _validate_content_size(content, resolved_encoding)
        target = _resolve_safe_path(base_dir, path, allowed_extensions=allowed_extensions)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding=resolved_encoding)
        timestamp = int(time.time())
        version_path = target.with_name(f"v{timestamp}_{target.name}")
        version_path.write_text(content, encoding=resolved_encoding)
        return ToolResult(
            success=True,
            output={
                "path": str(target),
                "version_path": str(version_path),
                "written_bytes": written_bytes,
                "version": timestamp,
            },
        )

    return handler


def build_filesystem_read_handler(
    output_dir: str,
    *,
    allowed_extensions: Iterable[str] = DEFAULT_ALLOWED_EXTENSIONS,
) -> Callable[..., Any]:
    base_dir = Path(output_dir)

    async def handler(path: str, encoding: str = "utf-8") -> ToolResult:
        resolved_encoding = _validate_encoding(encoding)
        target = _resolve_safe_path(base_dir, path, allowed_extensions=allowed_extensions)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError("File does not exist")
        content = target.read_text(encoding=resolved_encoding)
        return ToolResult(
            success=True,
            output={
                "path": str(target),
                "content": content,
            },
        )

    return handler


def build_validate_html_handler() -> Callable[..., Any]:
    async def handler(html: str) -> ToolResult:
        errors = validate_mobile_html(html or "")
        return ToolResult(
            success=True,
            output={
                "valid": len(errors) == 0,
                "errors": errors,
            },
        )

    return handler


def get_filesystem_tool_handlers(output_dir: str) -> Dict[str, Callable[..., Any]]:
    return {
        "filesystem_write": build_filesystem_write_handler(output_dir),
        "filesystem_read": build_filesystem_read_handler(output_dir),
    }


def get_all_tool_handlers(output_dir: str) -> Dict[str, Callable[..., Any]]:
    handlers = get_filesystem_tool_handlers(output_dir)
    handlers["validate_html"] = build_validate_html_handler()
    return handlers


__all__ = [
    "ALLOWED_ENCODINGS",
    "DEFAULT_ALLOWED_EXTENSIONS",
    "MAX_WRITE_BYTES",
    "build_filesystem_write_handler",
    "build_filesystem_read_handler",
    "build_validate_html_handler",
    "get_filesystem_tool_handlers",
    "get_all_tool_handlers",
]
