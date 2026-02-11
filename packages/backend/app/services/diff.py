"""File diff service for comparing file versions."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session as DbSession

from ..db.models import Page, PageVersion


class DiffService:
    """Service for generating file diffs."""

    def __init__(self, db: DbSession):
        self.db = db

    def get_page_version_diff(
        self,
        session_id: str,
        page_id: str,
        version_a: int | None = None,
        version_b: int | None = None,
    ) -> dict[str, Any] | None:
        """Get diff between two versions of a page.

        Args:
            session_id: Session ID
            page_id: Page ID
            version_a: Source version (older), None for previous
            version_b: Target version (newer), None for current

        Returns:
            Dict with 'old_content', 'new_content', 'diff_unified', 'stats'
        """
        page = self.db.query(Page).filter(
            Page.session_id == session_id,
            Page.id == page_id,
        ).first()

        if not page:
            return None

        # Get version_a (older)
        if version_a is None:
            # Get previous version
            current = self.db.query(PageVersion).filter(
                PageVersion.page_id == page.id,
            ).order_by(PageVersion.version.desc()).first()

            if current and current.version > 1:
                version_a = current.version - 1
            else:
                version_a = 1

        # Get version_b (newer)
        if version_b is None:
            version_b = self.db.query(PageVersion).filter(
                PageVersion.page_id == page.id,
            ).order_by(PageVersion.version.desc()).first()

            if version_b:
                version_b = version_b.version
            else:
                return None

        # Fetch both versions
        v_a = self.db.query(PageVersion).filter(
            PageVersion.page_id == page_id,
            PageVersion.version == version_a,
        ).first()

        v_b = self.db.query(PageVersion).filter(
            PageVersion.page_id == page_id,
            PageVersion.version == version_b,
        ).first()

        if not v_a or not v_b:
            return None

        old_content = v_a.html
        new_content = v_b.html

        # Generate unified diff
        unified = self._generate_unified_diff(old_content, new_content)

        # Calculate stats
        old_lines = old_content.count('\n') + 1
        new_lines = new_content.count('\n') + 1

        return {
            "page_id": page_id,
            "version_a": version_a,
            "version_b": version_b,
            "old_content": old_content,
            "new_content": new_content,
            "diff_unified": unified,
            "stats": {
                "old_lines": old_lines,
                "new_lines": new_lines,
            },
        }

    def _generate_unified_diff(self, old: str, new: str) -> str:
        """Generate unified diff between two strings."""
        unified = difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile="old",
            tofile="new",
            lineterm="",
        )
        return "".join(unified)


__all__ = ["DiffService"]
