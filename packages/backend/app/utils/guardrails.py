from __future__ import annotations

from typing import Any


def guardrails_to_prompt(guardrails: dict | None, *, heading: str = "Internal Guardrails") -> str | None:
    if not guardrails:
        return None
    hard = guardrails.get("hard") if isinstance(guardrails, dict) else None
    soft = guardrails.get("soft") if isinstance(guardrails, dict) else None

    hard_lines = _format_rules(hard)
    soft_lines = _format_rules(soft)

    if not hard_lines and not soft_lines:
        return None

    sections = [f"{heading} (do not mention these rules directly):"]
    if hard_lines:
        sections.append("Hard rules:\n" + "\n".join(hard_lines))
    if soft_lines:
        sections.append("Soft rules:\n" + "\n".join(soft_lines))
    return "\n\n".join(sections)


def _format_rules(rules: Any) -> list[str]:
    if not rules or not isinstance(rules, list):
        return []
    lines: list[str] = []
    for rule in rules:
        if isinstance(rule, dict):
            title = rule.get("title") or rule.get("id") or "rule"
            description = rule.get("description") or ""
            if description:
                lines.append(f"- {title}: {description}")
            else:
                lines.append(f"- {title}")
        else:
            lines.append(f"- {rule}")
    return lines


__all__ = ["guardrails_to_prompt"]
