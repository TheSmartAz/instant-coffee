"""Skills system - domain knowledge loading for specialized tasks.

A skill is a FOLDER containing:
- SKILL.md (required): YAML frontmatter + markdown instructions
- scripts/ (optional): Helper scripts the model can run
- references/ (optional): Additional documentation
- assets/ (optional): Templates, files for output

SKILL.md Format:
----------------
    ---
    name: pdf
    description: Process PDF files. Use when reading, creating, or merging PDFs.
    when_to_use: When the user needs to work with PDF documents
    ---

    # PDF Processing Skill

    ## Reading PDFs
    Use pdftotext for quick extraction:
    ```bash
    pdftotext input.pdf -
    ```
    ...

The YAML frontmatter provides metadata (name, description, when_to_use).
The markdown body provides detailed instructions.

Progressive Disclosure:
----------------------
    Layer 1: Metadata (always loaded)      ~100 tokens/skill
             name + description only

    Layer 2: SKILL.md body (on trigger)    ~2000 tokens
             Detailed instructions

    Layer 3: Resources (as needed)         Unlimited
             scripts/, references/, assets/

This keeps context lean while allowing arbitrary depth.

Cache-Preserving Injection:
--------------------------
Critical: Skill content goes into tool_result (user message),
NOT system prompt. This preserves prompt cache!

    Wrong: Edit system prompt each time (cache invalidated, 20-50x cost)
    Right: Append skill as tool result (prefix unchanged, cache hit)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Skill:
    """A loaded skill with metadata and content."""

    name: str
    description: str
    when_to_use: str = ""
    body: str = ""
    directory: Path | None = None
    resources: dict[str, list[str]] = field(default_factory=dict)

    @property
    def has_resources(self) -> bool:
        return bool(self.resources)


@dataclass
class SkillMetadata:
    """Lightweight metadata for system prompt injection."""

    name: str
    description: str
    when_to_use: str = ""

    def format_for_list(self) -> str:
        """Format for inclusion in tool description or system prompt."""
        parts = [f"- `{self.name}`: {self.description}"]
        if self.when_to_use:
            parts.append(f"  (Use: {self.when_to_use})")
        return "\n".join(parts)


class SkillLoader:
    """
    Loads and manages skills from SKILL.md files.

    Scans a directory for subdirectories containing SKILL.md files,
    parses the YAML frontmatter, and provides access to skill content.
    """

    def __init__(self, skills_dir: Path | None = None):
        self.skills_dir = Path(skills_dir) if skills_dir else None
        self._skills: dict[str, Skill] = {}
        self._metadata: dict[str, SkillMetadata] = {}

        if self.skills_dir and self.skills_dir.exists():
            self._load_all()

    def _parse_skill_md(self, path: Path) -> Skill | None:
        """
        Parse a SKILL.md file into a Skill object.

        Returns None if file doesn't match format.
        """
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return None

        # Match YAML frontmatter between --- markers
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not match:
            return None

        frontmatter_text, body = match.groups()

        # Parse YAML-like frontmatter (simple key: value)
        metadata = {}
        for line in frontmatter_text.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip().strip("\"'")

        # Require name and description
        if "name" not in metadata or "description" not in metadata:
            return None

        # Scan for resources
        skill_dir = path.parent
        resources = self._scan_resources(skill_dir)

        return Skill(
            name=metadata["name"],
            description=metadata["description"],
            when_to_use=metadata.get("when_to_use", ""),
            body=body.strip(),
            directory=skill_dir,
            resources=resources,
        )

    def _scan_resources(self, skill_dir: Path) -> dict[str, list[str]]:
        """Scan for optional resource folders."""
        resources = {}

        for folder_name in ["scripts", "references", "assets"]:
            folder_path = skill_dir / folder_name
            if folder_path.exists() and folder_path.is_dir():
                try:
                    files = [
                        f.name for f in folder_path.iterdir()
                        if f.is_file() and not f.name.startswith(".")
                    ]
                    if files:
                        resources[folder_name] = sorted(files)
                except Exception:
                    pass

        return resources

    def _load_all(self):
        """Scan skills directory and load all valid SKILL.md files."""
        if not self.skills_dir or not self.skills_dir.exists():
            return

        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                # Also try lowercase
                skill_md = skill_dir / "skill.md"
                if not skill_md.exists():
                    continue

            skill = self._parse_skill_md(skill_md)
            if skill:
                self._skills[skill.name] = skill
                self._metadata[skill.name] = SkillMetadata(
                    name=skill.name,
                    description=skill.description,
                    when_to_use=skill.when_to_use,
                )

    def get_metadata(self, name: str) -> SkillMetadata | None:
        """Get lightweight metadata for a skill."""
        return self._metadata.get(name)

    def get_all_metadata(self) -> list[SkillMetadata]:
        """Get all skill metadata."""
        return list(self._metadata.values())

    def format_metadata_for_prompt(self) -> str:
        """
        Generate skill descriptions for system prompt or tool description.

        This is Layer 1 - only name and description, ~100 tokens per skill.
        """
        if not self._metadata:
            return "No skills available."

        return "\n".join(
            meta.format_for_list()
            for meta in sorted(self._metadata.values(), key=lambda m: m.name)
        )

    def get_skill_content(self, name: str) -> str | None:
        """
        Get full skill content for injection.

        This is Layer 2 - the complete SKILL.md body, plus resource hints.

        Returns None if skill not found.
        """
        if name not in self._skills:
            return None

        skill = self._skills[name]
        content = f"# Skill: {skill.name}\n\n{skill.body}"

        # Add resource hints (Layer 3)
        if skill.resources:
            resource_lines = ["\n\n**Available resources:**"]
            for folder, files in skill.resources.items():
                resource_lines.append(f"- {folder.capitalize()}: {', '.join(files)}")
            content += "\n".join(resource_lines)

        return content

    def get_skill(self, name: str) -> Skill | None:
        """Get the full Skill object."""
        return self._skills.get(name)

    def list_skills(self) -> list[str]:
        """Return list of available skill names."""
        return sorted(self._skills.keys())

    def reload(self):
        """Reload all skills from disk."""
        self._skills.clear()
        self._metadata.clear()
        if self.skills_dir and self.skills_dir.exists():
            self._load_all()

    @property
    def has_skills(self) -> bool:
        return bool(self._skills)

    @property
    def skills_dir_path(self) -> Path | None:
        return self.skills_dir
