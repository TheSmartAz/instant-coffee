"""Lazy exports for LLM utilities to avoid import cycles."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    # openai_client
    "APIError": ("app.llm.openai_client", "APIError"),
    "AuthenticationError": ("app.llm.openai_client", "AuthenticationError"),
    "ContextLengthError": ("app.llm.openai_client", "ContextLengthError"),
    "LLMResponse": ("app.llm.openai_client", "LLMResponse"),
    "OpenAIClient": ("app.llm.openai_client", "OpenAIClient"),
    "OpenAIClientError": ("app.llm.openai_client", "OpenAIClientError"),
    "RateLimitError": ("app.llm.openai_client", "RateLimitError"),
    "TimeoutError": ("app.llm.openai_client", "TimeoutError"),
    "TokenUsage": ("app.llm.openai_client", "TokenUsage"),
    # client_factory
    "ModelClientFactory": ("app.llm.client_factory", "ModelClientFactory"),
    "ModelClientFactoryError": ("app.llm.client_factory", "ModelClientFactoryError"),
    # model_pool
    "FallbackTrigger": ("app.llm.model_pool", "FallbackTrigger"),
    "ModelCallResult": ("app.llm.model_pool", "ModelCallResult"),
    "ModelExhaustedError": ("app.llm.model_pool", "ModelExhaustedError"),
    "ModelPoolManager": ("app.llm.model_pool", "ModelPoolManager"),
    "ModelRole": ("app.llm.model_pool", "ModelRole"),
    "ModelSelection": ("app.llm.model_pool", "ModelSelection"),
    "get_model_pool_manager": ("app.llm.model_pool", "get_model_pool_manager"),
    "should_fallback": ("app.llm.model_pool", "should_fallback"),
    # tools
    "FILESYSTEM_READ_TOOL": ("app.llm.tools", "FILESYSTEM_READ_TOOL"),
    "FILESYSTEM_WRITE_TOOL": ("app.llm.tools", "FILESYSTEM_WRITE_TOOL"),
    "VALIDATE_HTML_TOOL": ("app.llm.tools", "VALIDATE_HTML_TOOL"),
    "ReadFileParams": ("app.llm.tools", "ReadFileParams"),
    "Tool": ("app.llm.tools", "Tool"),
    "ToolResult": ("app.llm.tools", "ToolResult"),
    "ValidateHtmlParams": ("app.llm.tools", "ValidateHtmlParams"),
    "WriteFileParams": ("app.llm.tools", "WriteFileParams"),
    "get_all_tools": ("app.llm.tools", "get_all_tools"),
    "get_filesystem_tools": ("app.llm.tools", "get_filesystem_tools"),
}


__all__ = sorted(_LAZY_EXPORTS.keys())


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if not target:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    module = import_module(module_name)
    value = getattr(module, attr)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_EXPORTS.keys()))
