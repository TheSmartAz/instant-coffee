from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


class Tool:
    def __init__(self, name: str, description: str, parameters: Dict[str, Any]) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters

    def to_openai_format(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class WriteFileParams:
    path: str
    content: str
    encoding: str = "utf-8"


@dataclass
class ReadFileParams:
    path: str
    encoding: str = "utf-8"


@dataclass
class ValidateHtmlParams:
    html: str


@dataclass
class ToolResult:
    success: bool
    output: Any = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"success": self.success}
        if self.output is not None:
            result["output"] = self.output
        if self.error is not None:
            result["error"] = self.error
        return result


FILESYSTEM_WRITE_TOOL = Tool(
    name="filesystem_write",
    description="Write content to a file. Use this to save generated HTML or other files.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The file path to write to"},
            "content": {"type": "string", "description": "The content to write"},
            "encoding": {
                "type": "string",
                "description": "File encoding (default: utf-8)",
                "enum": ["utf-8", "gbk"],
                "default": "utf-8",
            },
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    },
)

FILESYSTEM_READ_TOOL = Tool(
    name="filesystem_read",
    description="Read content from a file. Use this to load existing HTML or other files.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The file path to read"},
            "encoding": {
                "type": "string",
                "description": "File encoding (default: utf-8)",
                "enum": ["utf-8", "gbk"],
                "default": "utf-8",
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    },
)

VALIDATE_HTML_TOOL = Tool(
    name="validate_html",
    description=(
        "Validate HTML against mobile-first standards (viewport tag, 9:19.5 ratio, "
        "max width 430px, hidden scrollbars, touch target sizes)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "html": {"type": "string", "description": "HTML content to validate"},
        },
        "required": ["html"],
        "additionalProperties": False,
    },
)


def get_filesystem_tools() -> list[Tool]:
    return [FILESYSTEM_WRITE_TOOL, FILESYSTEM_READ_TOOL]


def get_all_tools() -> list[Tool]:
    return [FILESYSTEM_WRITE_TOOL, FILESYSTEM_READ_TOOL, VALIDATE_HTML_TOOL]


__all__ = [
    "FILESYSTEM_READ_TOOL",
    "FILESYSTEM_WRITE_TOOL",
    "VALIDATE_HTML_TOOL",
    "ReadFileParams",
    "Tool",
    "ToolResult",
    "ValidateHtmlParams",
    "WriteFileParams",
    "get_all_tools",
    "get_filesystem_tools",
]
