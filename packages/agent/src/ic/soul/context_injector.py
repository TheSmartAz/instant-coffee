"""Context injection - automatically gather and inject project context.

This module provides automatic context discovery and injection for the agent:
- Product doc discovery (product-doc.md)
- Git status injection
- Directory structure analysis
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ic.llm.provider import Message
from ic.soul.git_helper import get_git_status, GitStatus


@dataclass
class ContextConfig:
    """Configuration for what context to inject."""

    include_product_doc: bool = True
    include_git_status: bool = False  # Default: disabled for web sessions
    include_directory_tree: bool = True
    directory_max_depth: int = 2  # Reduced from 3
    directory_max_files: int = 30  # Reduced from 50
    # Alternative: flat file list instead of tree
    use_flat_file_list: bool = True  # Simpler format, no indentation
    product_doc_names: list[str] = field(default_factory=lambda: [
        "product-doc.md",
        "PRODUCT.md",
        "product.md",
    ])


@dataclass
class InjectedContext:
    """Result of context injection."""

    messages: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def format_for_system_prompt(self) -> str:
        """Format all injected context as a system prompt addition."""
        if not self.messages:
            return ""
        parts = []
        for msg in self.messages:
            if msg.content:
                parts.append(msg.content)
        return "\n\n".join(parts)


class ContextInjector:
    """Automatically collects and injects project context.

    This class gathers relevant context from the workspace and formats it
    for injection into the agent's conversation context.
    """

    def __init__(self, config: ContextConfig | None = None):
        self.config = config or ContextConfig()
        self._cache: dict[str, Any] = {}

    async def inject_all(
        self,
        workspace: Optional[Path] = None,
        force_refresh: bool = False,
    ) -> InjectedContext:
        """Inject all configured context types.

        Args:
            workspace: The workspace directory to analyze
            force_refresh: Bypass cache and re-fetch everything

        Returns:
            InjectedContext with messages ready to add to the conversation
        """
        if workspace is None:
            return InjectedContext()

        workspace = Path(workspace).resolve()
        messages = []
        metadata = {}

        # 1. Product doc discovery
        if self.config.include_product_doc and (
            force_refresh or "product_doc" not in self._cache
        ):
            product_doc = self._find_product_doc(workspace)
            if product_doc:
                messages.append(Message(
                    role="user",
                    content=self._format_product_doc(product_doc),
                ))
                metadata["product_doc_found"] = True
                metadata["product_doc_path"] = str(product_doc.relative_to(workspace))

        # 2. Git status
        if self.config.include_git_status and (
            force_refresh or "git_status" not in self._cache
        ):
            git_status = get_git_status(workspace)
            if git_status:
                messages.append(Message(
                    role="user",
                    content=self._format_git_status(git_status),
                ))
                metadata["git_status"] = True

        # 3. Directory structure
        if self.config.include_directory_tree and (
            force_refresh or "directory_tree" not in self._cache
        ):
            if self.config.use_flat_file_list:
                file_list = self._get_file_list(
                    workspace,
                    max_files=self.config.directory_max_files,
                )
                if file_list:
                    messages.append(Message(
                        role="user",
                        content=self._format_file_list(file_list, workspace),
                    ))
                    metadata["directory_tree"] = True
            else:
                tree = self._get_directory_tree(
                    workspace,
                    max_depth=self.config.directory_max_depth,
                    max_files=self.config.directory_max_files,
                )
                if tree:
                    messages.append(Message(
                        role="user",
                        content=self._format_directory_tree(tree),
                    ))
                    metadata["directory_tree"] = True

        return InjectedContext(messages=messages, metadata=metadata)

    async def reinject_after_compaction(
        self,
        workspace: Path,
        project_state: dict | None = None,
    ) -> list[Message]:
        """Re-inject critical context after compaction.

        Unlike inject_all(), this always runs (no _context_injected guard)
        and returns messages to be added to context.

        Args:
            workspace: The workspace directory
            project_state: Optional project state dict from DB with pages,
                product_doc summary, design decisions, etc.
        """
        messages = []

        # Re-inject product doc
        if self.config.include_product_doc:
            product_doc = self._find_product_doc(workspace)
            if product_doc:
                messages.append(Message(
                    role="user",
                    content=self._format_product_doc(product_doc),
                ))

        # Re-inject file list
        if self.config.include_directory_tree:
            if self.config.use_flat_file_list:
                file_list = self._get_file_list(workspace, max_files=self.config.directory_max_files)
                if file_list:
                    messages.append(Message(
                        role="user",
                        content=self._format_file_list(file_list, workspace),
                    ))

        # Inject project state (pages, versions, design decisions)
        if project_state:
            state_xml = self._format_project_state(project_state)
            if state_xml:
                messages.append(Message(
                    role="user",
                    content=state_xml,
                ))

        return messages

    @staticmethod
    def _format_project_state(state: dict) -> str:
        """Format project state as XML for injection into context."""
        parts = ["<project_state>"]

        # Product doc summary
        doc = state.get("product_doc")
        if doc:
            parts.append(f"  <product_doc status=\"{state.get('product_doc_status', 'draft')}\" "
                         f"version=\"{state.get('product_doc_version', 1)}\">"
                         f"{doc[:500]}...</product_doc>")

        # Pages inventory
        pages = state.get("pages", [])
        if pages:
            parts.append("  <pages>")
            for p in pages:
                slug = p.get("slug", "")
                title = p.get("title", "")
                version = p.get("version", "")
                desc = p.get("description", "")
                parts.append(f'    <page slug="{slug}" title="{title}" '
                             f'version="{version}" description="{desc}"/>')
            parts.append("  </pages>")

        # Design decisions (if provided)
        decisions = state.get("design_decisions")
        if decisions:
            parts.append(f"  <design_decisions>{decisions}</design_decisions>")

        parts.append("</project_state>")
        return "\n".join(parts) if len(parts) > 2 else ""

    def _find_product_doc(self, workspace: Path) -> Optional[Path]:
        """Find product doc file by trying various names."""
        for name in self.config.product_doc_names:
            path = workspace / name
            if path.exists() and path.is_file():
                return path
        return None

    def _format_product_doc(self, doc_path: Path) -> str:
        """Format product doc content for LLM consumption."""
        try:
            content = doc_path.read_text(encoding="utf-8")
            # Truncate if too long
            if len(content) > 10_000:
                content = content[:9_500] + "\n\n... (truncated)"
            return f"""<project_documentation>
File: {doc_path.name}

```markdown
{content}
```
</project_documentation>"""
        except Exception:
            return ""

    def _format_git_status(self, status: GitStatus) -> str:
        """Format git status for LLM consumption."""
        return f"""<git_status>
{status.format()}
</git_status>"""

    def _format_directory_tree(self, tree: str) -> str:
        """Format directory tree for LLM consumption."""
        return f"""<project_structure>
```
{tree}
```
</project_structure>"""

    def _format_file_list(self, files: list[str], workspace: Path) -> str:
        """Format flat file list for LLM consumption."""
        return f"""<project_files>
{len(files)} files in workspace:
{chr(10).join(f"  - {f}" for f in files)}
</project_files>"""

    def _get_file_list(
        self,
        workspace: Path,
        max_files: int = 30,
    ) -> list[str]:
        """Get a flat list of files (not directories).

        Returns sorted list of relative file paths.
        """
        try:
            hidden_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", ".idea", ".vscode"}
            files = []

            for entry in workspace.rglob("*"):
                if entry.is_file():
                    # Skip hidden directories
                    if any(hidden in entry.parts for hidden in hidden_dirs):
                        continue
                    # Skip hidden files
                    if entry.name.startswith("."):
                        continue
                    rel_path = entry.relative_to(workspace)
                    files.append(str(rel_path))
                    if len(files) >= max_files:
                        break

            return sorted(files)
        except Exception:
            return []

    def _get_directory_tree(
        self,
        workspace: Path,
        max_depth: int = 3,
        max_files: int = 50,
    ) -> Optional[str]:
        """Generate directory tree representation.

        Args:
            workspace: Root directory to scan
            max_depth: Maximum directory depth
            max_files: Maximum number of files to show

        Returns:
            String representation of the tree, or None if empty
        """
        try:
            lines = []
            file_count = 0
            hidden_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", ".idea", ".vscode"}

            def _scan(path: Path, depth: int, prefix: str = ""):
                nonlocal file_count
                if depth > max_depth or file_count >= max_files:
                    return

                try:
                    entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
                except PermissionError:
                    return

                for i, entry in enumerate(entries):
                    if entry.name.startswith(".") or entry.name in hidden_dirs:
                        continue

                    is_last = i == len(entries) - 1
                    connector = "└── " if is_last else "├── "
                    lines.append(f"{prefix}{connector}{entry.name}")

                    if entry.is_dir():
                        file_count += 1
                        next_prefix = prefix + ("    " if is_last else "│   ")
                        _scan(entry, depth + 1, next_prefix)
                    else:
                        file_count += 1

                    if file_count >= max_files:
                        if depth < max_depth:
                            lines.append(f"{prefix}... (truncated, max {max_files} files)")
                        return

            _scan(workspace, 0)
            return "\n".join(lines) if lines else None

        except Exception:
            return None

    def clear_cache(self):
        """Clear cached context data."""
        self._cache.clear()

    def set_cache(self, key: str, value: Any):
        """Manually set a cached value."""
        self._cache[key] = value
