from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

PolicyAction = Literal["allow", "warn", "block"]


@dataclass
class ToolPolicyContext:
    tool_name: str
    arguments: Any
    session_id: Optional[str] = None
    run_id: Optional[str] = None


@dataclass
class PolicyResult:
    action: PolicyAction
    policy: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PostPolicyResult:
    result: dict[str, Any]
    findings: list[PolicyResult]


class ToolPolicyService:
    _PATH_KEYS = {
        "path",
        "paths",
        "file",
        "files",
        "filepath",
        "filename",
        "source",
        "target",
        "src",
        "dst",
        "dir",
        "directory",
        "cwd",
        "workdir",
        "output_dir",
        "input_path",
        "output_path",
    }

    _SHELL_TOOL_HINTS = (
        "shell",
        "exec",
        "command",
        "terminal",
        "bash",
    )

    _SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
        ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
        ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9\-\._=]{16,}\b", re.IGNORECASE)),
        (
            "credential_assignment",
            re.compile(r"\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,}", re.IGNORECASE),
        ),
    )

    _SENSITIVE_FIELD_NAMES = {"api_key", "token", "secret", "password", "authorization", "auth"}

    def __init__(self, settings: Any, *, project_root: Path | None = None) -> None:
        self.settings = settings
        self.enabled = bool(getattr(settings, "tool_policy_enabled", True))
        self.mode = self._normalize_mode(getattr(settings, "tool_policy_mode", "log_only"))
        prefixes = getattr(settings, "tool_policy_allowed_cmd_prefixes", None)
        if isinstance(prefixes, (list, tuple, set)):
            self.allowed_cmd_prefixes = {str(item).strip() for item in prefixes if str(item).strip()}
        else:
            self.allowed_cmd_prefixes = set()
        if not self.allowed_cmd_prefixes:
            self.allowed_cmd_prefixes = {
                "npm",
                "npx",
                "node",
                "python",
                "pip",
                "git",
                "ls",
                "cat",
                "echo",
                "mkdir",
                "cp",
            }
        threshold = getattr(settings, "tool_policy_large_output_bytes", 100 * 1024)
        try:
            self.large_output_bytes = max(int(threshold), 1024)
        except Exception:
            self.large_output_bytes = 100 * 1024
        self.project_root = (project_root or Path.cwd()).resolve()

    def pre_tool_use(self, context: ToolPolicyContext) -> list[PolicyResult]:
        if not self.enabled or self.mode == "off":
            return []

        findings: list[PolicyResult] = []
        command_finding = self._check_command_whitelist(context)
        if command_finding is not None:
            findings.append(self._apply_mode(command_finding))

        path_finding = self._check_path_boundary(context.arguments)
        if path_finding is not None:
            findings.append(self._apply_mode(path_finding))

        sensitive_finding = self._check_sensitive_content(context.arguments, location="arguments")
        if sensitive_finding is not None:
            findings.append(self._apply_mode(sensitive_finding))

        return findings

    def post_tool_use(self, context: ToolPolicyContext, result: dict[str, Any]) -> PostPolicyResult:
        safe_result = dict(result or {})
        if not self.enabled or self.mode == "off":
            return PostPolicyResult(result=safe_result, findings=[])

        findings: list[PolicyResult] = []

        sensitive_finding = self._check_sensitive_content(safe_result, location="result")
        if sensitive_finding is not None:
            findings.append(self._apply_mode(sensitive_finding))

        safe_result, truncation_finding = self._truncate_large_output(safe_result)
        if truncation_finding is not None:
            findings.append(self._apply_mode(truncation_finding))

        return PostPolicyResult(result=safe_result, findings=findings)

    def _normalize_mode(self, mode: Any) -> str:
        normalized = str(mode or "").strip().lower()
        if normalized in {"off", "log_only", "enforce"}:
            return normalized
        return "log_only"

    def _apply_mode(self, finding: PolicyResult) -> PolicyResult:
        if self.mode == "log_only" and finding.action == "block":
            return PolicyResult(
                action="warn",
                policy=finding.policy,
                reason=finding.reason,
                details=dict(finding.details),
            )
        return finding

    def _check_command_whitelist(self, context: ToolPolicyContext) -> PolicyResult | None:
        if not self._is_shell_tool(context.tool_name):
            return None

        command = self._extract_command(context.arguments)
        if not command:
            return None
        command = command.strip()
        if not command:
            return None

        try:
            tokens = shlex.split(command)
        except Exception:
            tokens = command.split()
        if not tokens:
            return None

        command_prefix = tokens[0]
        if "/" in command_prefix:
            command_prefix = Path(command_prefix).name

        if command_prefix in self.allowed_cmd_prefixes:
            return None

        return PolicyResult(
            action="block",
            policy="command_whitelist",
            reason=f"Command '{command_prefix}' not in allowed prefixes",
            details={
                "command_prefix": command_prefix,
                "allowed_prefixes": sorted(self.allowed_cmd_prefixes),
            },
        )

    def _check_path_boundary(self, value: Any) -> PolicyResult | None:
        for candidate in self._collect_candidate_paths(value):
            normalized = candidate.strip()
            if not normalized:
                continue
            if "://" in normalized:
                continue

            raw_path = Path(normalized)
            if raw_path.is_absolute():
                resolved = raw_path.resolve()
            else:
                resolved = (self.project_root / raw_path).resolve()

            try:
                resolved.relative_to(self.project_root)
            except ValueError:
                return PolicyResult(
                    action="block",
                    policy="path_boundary",
                    reason=f"Path '{normalized}' is outside project directory",
                    details={
                        "path": normalized,
                        "resolved_path": str(resolved),
                        "project_root": str(self.project_root),
                    },
                )

        return None

    def _check_sensitive_content(self, value: Any, *, location: str) -> PolicyResult | None:
        for field_name, field_value in self._iter_fields(value):
            lowered = field_name.lower()
            if lowered in self._SENSITIVE_FIELD_NAMES and self._has_non_empty_value(field_value):
                return PolicyResult(
                    action="block",
                    policy="sensitive_content",
                    reason=f"Sensitive field '{field_name}' detected in {location}",
                    details={"location": location, "field": field_name},
                )

        text = self._safe_json_text(value)
        if not text:
            return None

        for pattern_name, pattern in self._SENSITIVE_PATTERNS:
            if pattern.search(text):
                return PolicyResult(
                    action="block",
                    policy="sensitive_content",
                    reason=f"Sensitive content pattern '{pattern_name}' detected in {location}",
                    details={"location": location, "pattern": pattern_name},
                )

        return None

    def _truncate_large_output(self, result: dict[str, Any]) -> tuple[dict[str, Any], PolicyResult | None]:
        if "output" not in result:
            return result, None

        output_value = result.get("output")
        text = self._safe_json_text(output_value)
        if not text:
            return result, None

        size = len(text.encode("utf-8", errors="ignore"))
        if size <= self.large_output_bytes:
            return result, None

        preview_limit = max(256, min(self.large_output_bytes // 4, 2048))
        truncated = {
            "truncated": True,
            "preview": text[:preview_limit],
            "original_size": size,
            "max_size": self.large_output_bytes,
        }

        updated = dict(result)
        updated["output"] = truncated
        finding = PolicyResult(
            action="warn",
            policy="large_output_truncate",
            reason="Tool output exceeded configured size limit and was truncated",
            details={
                "original_size": size,
                "max_size": self.large_output_bytes,
            },
        )
        return updated, finding

    def _is_shell_tool(self, tool_name: str) -> bool:
        lowered = (tool_name or "").strip().lower()
        if not lowered:
            return False
        return any(hint in lowered for hint in self._SHELL_TOOL_HINTS)

    def _extract_command(self, arguments: Any) -> str | None:
        if isinstance(arguments, str):
            return arguments
        if isinstance(arguments, dict):
            for key in ("cmd", "command"):
                value = arguments.get(key)
                if isinstance(value, str) and value.strip():
                    return value
            value = arguments.get("args")
            if isinstance(value, list) and value:
                if all(isinstance(item, str) for item in value):
                    return " ".join(value)
            value = arguments.get("value")
            if isinstance(value, str) and value.strip():
                return value
        return None

    def _collect_candidate_paths(self, value: Any) -> list[str]:
        collected: list[str] = []
        self._collect_paths_recursive(value, collected)
        return collected

    def _collect_paths_recursive(self, value: Any, collected: list[str]) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_name = str(key).lower()
                if key_name in self._PATH_KEYS:
                    if isinstance(item, str):
                        collected.append(item)
                    elif isinstance(item, (list, tuple, set)):
                        for part in item:
                            if isinstance(part, str):
                                collected.append(part)
                else:
                    self._collect_paths_recursive(item, collected)
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                self._collect_paths_recursive(item, collected)

    def _iter_fields(self, value: Any) -> list[tuple[str, Any]]:
        fields: list[tuple[str, Any]] = []

        def _walk(node: Any) -> None:
            if isinstance(node, dict):
                for key, item in node.items():
                    fields.append((str(key), item))
                    _walk(item)
            elif isinstance(node, (list, tuple, set)):
                for item in node:
                    _walk(item)

        _walk(value)
        return fields

    def _safe_json_text(self, value: Any) -> str:
        if value is None:
            return ""
        try:
            return json.dumps(value, ensure_ascii=False, default=str)
        except TypeError:
            return str(value)

    def _has_non_empty_value(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, set, dict)):
            return bool(value)
        return True


__all__ = [
    "PolicyResult",
    "PostPolicyResult",
    "ToolPolicyContext",
    "ToolPolicyService",
]
