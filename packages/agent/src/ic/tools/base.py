"""Base tool class for the agent tool system."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolParam:
    """A single tool parameter."""

    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    enum: list[str] | None = None


@dataclass
class ToolResult:
    """Result from a tool execution."""

    output: str = ""
    error: str | None = None
    is_error: bool = False

    def to_content(self) -> str:
        if self.is_error:
            return f"Error: {self.error}"
        return self.output


class BaseTool(ABC):
    """Base class for all tools. Subclass and implement execute()."""

    name: str = ""
    description: str = ""
    parameters: list[ToolParam] = []

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given arguments."""
        ...

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function calling schema."""
        properties = {}
        required = []
        for p in self.parameters:
            prop: dict[str, Any] = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
            if p.required:
                required.append(p.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
