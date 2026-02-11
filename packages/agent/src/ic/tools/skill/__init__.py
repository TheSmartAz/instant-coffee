"""ExecuteSkill tool - loads domain knowledge for specialized tasks.

When the model encounters a task that requires specialized knowledge
(PDF processing, MCP development, code review patterns, etc.),
it uses this tool to load a SKILL.md file that provides detailed
instructions and resources.

This implements "progressive disclosure" - only skill metadata is
in the system prompt initially; full content is loaded on-demand.
"""

from __future__ import annotations

from pathlib import Path

from ic.tools.base import BaseTool, ToolParam, ToolResult, ToolCompleteEvent
from ic.soul.skills import SkillLoader


class ExecuteSkill(BaseTool):
    """Load a skill to gain specialized knowledge for a task.

    The skill content will be injected into the conversation,
    giving the model detailed instructions and access to resources.
    """

    name = "execute_skill"
    description = (
        "Load a skill to gain specialized knowledge for a task. "
        "Use IMMEDIATELY when user task matches a skill description. "
        "The skill content will be injected with detailed instructions."
    )
    parameters = [
        ToolParam(
            name="skill",
            type="string",
            description="Name of the skill to load (e.g., 'pdf', 'mcp-builder')",
            required=True,
        ),
    ]

    def __init__(
        self,
        skill_loader: SkillLoader | None = None,
        workspace: Path | None = None,
    ):
        super().__init__()
        self._skill_loader = skill_loader
        self._workspace = workspace

    def set_skill_loader(self, skill_loader: SkillLoader):
        """Set or update the skill loader."""
        self._skill_loader = skill_loader

    def _update_description(self):
        """Update tool description with current skill list."""
        if self._skill_loader and self._skill_loader.has_skills:
            skills_list = self._skill_loader.format_metadata_for_prompt()
            self.description = (
                f"Load a skill to gain specialized knowledge for a task.\n\n"
                f"Available skills:\n{skills_list}\n\n"
                f"Use IMMEDIATELY when user task matches a skill description."
            )
        else:
            self.description = (
                "Load a skill to gain specialized knowledge for a task. "
                "(No skills currently available)"
            )

    async def execute(self, skill: str) -> ToolResult:
        """Execute the skill loading (simple interface)."""
        async for event in self.execute_stream(skill=skill):
            if isinstance(event, ToolCompleteEvent):
                return ToolResult(output=event.output)
        return ToolResult(output="")

    async def execute_stream(self, skill: str):
        """Execute with streaming progress support."""
        await self._emit_progress(f"Loading skill: {skill}...")

        if not self._skill_loader:
            yield ToolCompleteEvent(
                output="Error: No skill loader configured."
            )
            return

        content = self._skill_loader.get_skill_content(skill)

        if content is None:
            available = ", ".join(self._skill_loader.list_skills()) or "none"
            yield ToolCompleteEvent(
                output=f"Error: Unknown skill '{skill}'. Available: {available}"
            )
            return

        await self._emit_progress("Skill loaded successfully.", 100)

        # Wrap in tags so model knows it's skill content
        # This is injected as a tool_result (user message), preserving cache
        output = f"""<skill-loaded name="{skill}">
{content}
</skill-loaded>

Follow the instructions in the skill above to complete the user's task."""

        yield ToolCompleteEvent(output=output)
