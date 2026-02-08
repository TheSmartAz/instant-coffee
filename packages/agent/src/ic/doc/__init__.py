"""ProductDoc — sectioned Markdown document as source of truth.

The product doc captures the full specification of what the agent should build.
It is human-readable, sectioned for incremental updates, and persisted with
the project.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Standard section names (order matters)
STANDARD_SECTIONS = [
    "Overview & Purpose",
    "Page Structure",
    "Visual Style",
    "Content & Copy",
    "Interactions & Features",
    "Assets & Media",
    "Technical Constraints",
]

SECTION_HINTS = {
    "Overview & Purpose": (
        "Page type, target audience, core purpose, key message, business goal"
    ),
    "Page Structure": (
        "Header/navigation, hero section, content sections (ordered), "
        "footer, page flow/routing"
    ),
    "Visual Style": (
        "Color palette, typography, visual mood, imagery style"
    ),
    "Content & Copy": (
        "Headlines, body text, CTAs, placeholder content notes"
    ),
    "Interactions & Features": (
        "Buttons/actions, forms, modals/dialogs, animations, user flows"
    ),
    "Assets & Media": (
        "Image descriptions, icon style, font sources, external resources"
    ),
    "Technical Constraints": (
        "Mobile-first viewport, responsive breakpoints, performance, "
        "accessibility, browser support"
    ),
}


@dataclass
class Section:
    """A single section of the product doc."""
    name: str
    content: str = ""
    level: int = 2  # markdown heading level


@dataclass
class ProductDoc:
    """Sectioned Markdown product document."""

    title: str = ""
    sections: list[Section] = field(default_factory=list)

    # ── Factory ──────────────────────────────────────────

    @classmethod
    def create_empty(cls, title: str = "Untitled Project") -> ProductDoc:
        """Create a new product doc with standard empty sections."""
        doc = cls(title=title)
        for name in STANDARD_SECTIONS:
            hint = SECTION_HINTS.get(name, "")
            doc.sections.append(Section(
                name=name,
                content=f"<!-- {hint} -->" if hint else "",
            ))
        return doc

    # ── Section access ───────────────────────────────────

    def get_section(self, name: str) -> Section | None:
        """Get a section by name (case-insensitive)."""
        name_lower = name.lower()
        for s in self.sections:
            if s.name.lower() == name_lower:
                return s
        return None

    def update_section(self, name: str, content: str) -> bool:
        """Update a section's content. Returns True if found."""
        section = self.get_section(name)
        if section:
            section.content = content
            return True
        return False

    def add_section(self, name: str, content: str = "", level: int = 2):
        """Add a new section at the end."""
        self.sections.append(Section(name=name, content=content, level=level))

    @property
    def section_names(self) -> list[str]:
        return [s.name for s in self.sections]

    # ── Serialization ────────────────────────────────────

    def to_markdown(self) -> str:
        """Serialize to Markdown string."""
        lines: list[str] = []
        if self.title:
            lines.append(f"# Product Doc: {self.title}")
            lines.append("")

        for section in self.sections:
            prefix = "#" * section.level
            lines.append(f"{prefix} {section.name}")
            lines.append("")
            if section.content:
                lines.append(section.content)
                lines.append("")

        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, text: str) -> ProductDoc:
        """Parse a Markdown string into a ProductDoc."""
        doc = cls()
        lines = text.split("\n")
        i = 0

        # Parse title (# Product Doc: ...)
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("# "):
                title = line[2:].strip()
                if title.lower().startswith("product doc:"):
                    title = title[len("product doc:"):].strip()
                doc.title = title
                i += 1
                break
            elif line:
                # No title line found, don't skip content
                break
            i += 1

        # Parse sections
        current_section: Section | None = None
        content_lines: list[str] = []

        while i < len(lines):
            line = lines[i]
            heading = _parse_heading(line)

            if heading:
                # Save previous section
                if current_section is not None:
                    current_section.content = "\n".join(
                        content_lines
                    ).strip()
                    doc.sections.append(current_section)

                level, name = heading
                current_section = Section(name=name, level=level)
                content_lines = []
            else:
                content_lines.append(line)

            i += 1

        # Save last section
        if current_section is not None:
            current_section.content = "\n".join(content_lines).strip()
            doc.sections.append(current_section)

        return doc

    # ── File I/O ─────────────────────────────────────────

    def save(self, path: Path):
        """Write to a Markdown file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> ProductDoc | None:
        """Load from a Markdown file. Returns None if file doesn't exist."""
        if not path.exists():
            return None
        return cls.from_markdown(path.read_text(encoding="utf-8"))

    # ── Summary ──────────────────────────────────────────

    def summary(self) -> str:
        """Short summary of doc completeness."""
        filled = sum(
            1 for s in self.sections
            if s.content and not s.content.startswith("<!--")
        )
        total = len(self.sections)
        return f"{self.title} ({filled}/{total} sections filled)"


def _parse_heading(line: str) -> tuple[int, str] | None:
    """Parse a markdown heading line. Returns (level, text) or None."""
    m = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
    if m:
        return len(m.group(1)), m.group(2).strip()
    return None
