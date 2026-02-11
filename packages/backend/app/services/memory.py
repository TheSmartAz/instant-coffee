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
]


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

        colors = set()
        fonts = set()

        for tc in tool_calls:
            args_str = str(tc.get("arguments", ""))
            # Extract colors
            for match in color_pattern.findall(args_str):
                colors.add(match)
            # Extract fonts
            for match in font_pattern.findall(args_str):
                font = match.strip().split(",")[0].strip(" '\"")
                if font and len(font) < 50:
                    fonts.add(font)

        if colors:
            existing = self.get_value(session_id, "style_preferences") or ""
            color_str = ", ".join(sorted(colors))
            if color_str not in existing:
                new_val = f"{existing}\nColors: {color_str}" if existing else f"Colors: {color_str}"
                self.save_memory(session_id, "style_preferences", new_val.strip())

        if fonts:
            existing = self.get_value(session_id, "style_preferences") or ""
            font_str = ", ".join(sorted(fonts))
            if font_str not in existing:
                new_val = f"{existing}\nFonts: {font_str}" if existing else f"Fonts: {font_str}"
                self.save_memory(session_id, "style_preferences", new_val.strip())
