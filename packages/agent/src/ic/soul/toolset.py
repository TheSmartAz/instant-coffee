"""Toolset - dynamic tool loading and management."""

from __future__ import annotations

import importlib
from typing import Any

from ic.tools.base import BaseTool


class Toolset:
    """Manages a collection of tools with dynamic loading."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def add(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    @property
    def tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def to_openai_schemas(self) -> list[dict[str, Any]]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def load_from_paths(self, paths: list[str], **deps: Any):
        """Load tools from module:ClassName paths.

        Args:
            paths: List of "module.path:ClassName" strings
            **deps: Dependencies to inject (e.g. engine=engine_instance)
        """
        for path in paths:
            try:
                module_path, class_name = path.rsplit(":", 1)
                module = importlib.import_module(module_path)
                tool_cls = getattr(module, class_name)
                tool = self._instantiate(tool_cls, deps)
                self.add(tool)
            except Exception as e:
                import sys
                print(f"Warning: Failed to load tool {path}: {e}", file=sys.stderr)

    def _instantiate(self, tool_cls: type, deps: dict[str, Any]) -> BaseTool:
        """Instantiate a tool class, injecting dependencies if needed."""
        import inspect

        # Check if the class defines its own __init__ (not inherited from object/BaseTool)
        has_own_init = "__init__" in tool_cls.__dict__
        if not has_own_init:
            return tool_cls()

        sig = inspect.signature(tool_cls.__init__)
        kwargs = {}
        for p in list(sig.parameters.values())[1:]:  # skip self
            # Only handle normal keyword params, skip *args/**kwargs
            if p.kind not in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            ):
                continue
            if p.name in deps:
                kwargs[p.name] = deps[p.name]
            elif p.default is not inspect.Parameter.empty:
                pass
            else:
                kwargs[p.name] = None
        return tool_cls(**kwargs)
