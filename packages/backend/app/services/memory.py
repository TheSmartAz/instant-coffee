"""Project memory service for session resume.

Stores and retrieves persistent key-value memory per session,
enabling the agent to remember style preferences, design decisions,
and component inventory across session resumes.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session as DbSession

from ..db.models import ProjectMemory
from ..utils.datetime import utcnow

logger = logging.getLogger(__name__)

# Standard memory keys
MEMORY_KEYS = [
    "style_preferences",
    "component_inventory",
    "design_decisions",
    "user_preferences",
    "architecture_notes",
    "interface_contracts",
    "testing_notes",
]


def _append_unique(existing: str, heading: str, values: set[str]) -> str:
    if not values:
        return existing
    current = existing or ""
    lines = [line.strip() for line in current.splitlines()]
    additions = [item for item in sorted(values) if item and item not in current]
    if not additions:
        return current.strip()
    section = [f"{heading}: {', '.join(additions)}"]
    return "\n".join([*lines, *section]).strip() if lines else "\n".join(section)


class ProjectMemoryService:
    """Service for managing persistent project memory."""

    def __init__(self, db: DbSession):
        self.db = db

    def save_memory(self, session_id: str, key: str, value: str) -> None:
        """Save or update a memory entry."""
        existing = (
            self.db.query(ProjectMemory)
            .filter_by(session_id=session_id, key=key)
            .first()
        )
        if existing:
            existing.value = value
            existing.updated_at = utcnow()
        else:
            self.db.add(ProjectMemory(
                session_id=session_id,
                key=key,
                value=value,
            ))
        self.db.commit()

    def get_memory(self, session_id: str) -> dict[str, str]:
        """Get all memory entries for a session."""
        entries = (
            self.db.query(ProjectMemory)
            .filter_by(session_id=session_id)
            .all()
        )
        return {e.key: e.value for e in entries}

    def get_value(self, session_id: str, key: str) -> Optional[str]:
        """Get a single memory value."""
        entry = (
            self.db.query(ProjectMemory)
            .filter_by(session_id=session_id, key=key)
            .first()
        )
        return entry.value if entry else None

    def build_memory_context(self, session_id: str) -> str:
        """Build a context string from all memory entries for prompt injection."""
        memory = self.get_memory(session_id)
        if not memory:
            return ""

        parts = ["<project_memory>"]
        for key, value in memory.items():
            parts.append(f"  <{key}>{value}</{key}>")
        parts.append("</project_memory>")
        return "\n".join(parts)

    def build_memory_summary(self, session_id: str) -> dict[str, str]:
        """Return known memory entries limited to standard agent context keys."""
        memory = self.get_memory(session_id)
        return {
            key: value
            for key, value in memory.items()
            if key in MEMORY_KEYS and value.strip()
        }

    def extract_and_save_decisions(
        self, session_id: str, tool_calls: list[dict]
    ) -> None:
        """Extract design decisions from tool calls and save to memory.

        Looks for patterns in write_file/edit_file calls that indicate
        design choices (colors, fonts, layout patterns).
        """
        import re

        color_pattern = re.compile(r"#[0-9a-fA-F]{3,8}")
        font_pattern = re.compile(
            r"font-family:\s*['\"]?([^;'\"]+)['\"]?", re.IGNORECASE
        )
        file_path_pattern = re.compile(r'"file_path"\s*:\s*"([^"]+)"')

        colors = set()
        fonts = set()
        architecture_notes: set[str] = set()
        interface_contracts: set[str] = set()
        testing_notes: set[str] = set()

        for tc in tool_calls:
            args_str = str(tc.get("arguments", ""))
            tool_name = str(tc.get("name", ""))
            # Extract colors
            for match in color_pattern.findall(args_str):
                colors.add(match)
            # Extract fonts
            for match in font_pattern.findall(args_str):
                font = match.strip().split(",")[0].strip(" '\"")
                if font and len(font) < 50:
                    fonts.add(font)
            for path in file_path_pattern.findall(args_str):
                normalized = path.replace("\\", "/")
                if normalized.endswith((".tsx", ".ts", ".jsx", ".js", ".py")):
                    architecture_notes.add(f"Modified code path `{normalized}`")
                if "/api/" in normalized or "/schemas/" in normalized or "/types/" in normalized:
                    interface_contracts.add(f"Contract-bearing file `{normalized}`")
                if "test" in normalized.lower() or normalized.endswith((".spec.ts", ".test.ts", ".test.mjs")):
                    testing_notes.add(f"Test file `{normalized}`")
            if tool_name in {"shell", "grep_files"}:
                lower_args = args_str.lower()
                if "pytest" in lower_args:
                    testing_notes.add("Uses pytest for backend verification")
                if "npm run lint" in lower_args:
                    testing_notes.add("Uses npm run lint for web verification")
                if "npm run build" in lower_args:
                    testing_notes.add("Uses npm run build for web build verification")

        if colors:
            updated = _append_unique(
                self.get_value(session_id, "style_preferences") or "",
                "Colors",
                colors,
            )
            if updated:
                self.save_memory(session_id, "style_preferences", updated)

        if fonts:
            updated = _append_unique(
                self.get_value(session_id, "style_preferences") or "",
                "Fonts",
                fonts,
            )
            if updated:
                self.save_memory(session_id, "style_preferences", updated)

        if architecture_notes:
            updated = _append_unique(
                self.get_value(session_id, "architecture_notes") or "",
                "Code paths",
                architecture_notes,
            )
            if updated:
                self.save_memory(session_id, "architecture_notes", updated)

        if interface_contracts:
            updated = _append_unique(
                self.get_value(session_id, "interface_contracts") or "",
                "Contracts",
                interface_contracts,
            )
            if updated:
                self.save_memory(session_id, "interface_contracts", updated)

        if testing_notes:
            updated = _append_unique(
                self.get_value(session_id, "testing_notes") or "",
                "Verification",
                testing_notes,
            )
            if updated:
                self.save_memory(session_id, "testing_notes", updated)
