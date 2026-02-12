"""Main application - ties everything together."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ic.config import Config, AgentConfig, run_setup
from ic.doc import ProductDoc
from ic.session import ProjectStore, Project
from ic.soul.engine import Engine
from ic.soul.context import Context
from ic.ui.console import Console
from ic.ui.cli_io import CLIUserIO
from ic.ui.prompt import Prompt


SYSTEM_PROMPT = """\
You are an expert coding assistant that builds mobile-optimized web pages.

## Workflow

You follow a **Product Doc first** workflow:

1. **Interview** (REQUIRED): Always start by asking the user clarifying questions
   using the `ask_user` tool. Ask 2-5 multiple-choice questions per round.
   You MUST ask at least ONE round of questions before creating the Product Doc,
   even if the user's initial request seems detailed. There are always aspects
   worth clarifying: visual style preferences, specific content, interaction
   details, color palette, layout choices, etc.
   Adapt the number of follow-up rounds to how much info you still need
   (typically 1-3 rounds total).

2. **Build Product Doc**: Create or update `PRODUCT.md` in the workspace.
   This is the source of truth for what to build. It has these sections:
   - Overview & Purpose
   - Page Structure
   - Visual Style
   - Content & Copy
   - Interactions & Features
   - Assets & Media
   - Technical Constraints

3. **Confirm before first generation**: After creating the Product Doc for the
   first time, output a brief summary (2-4 sentences) of what was defined,
   then ask the user in plain text whether to proceed with generation.
   Example: "Product Doc is ready. Here's what I'll build: [summary].
   Shall I start generating?"
   IMPORTANT: Do NOT use the `ask_user` tool for this confirmation — just
   write it as normal text and stop. Wait for the user to reply.

4. **Generate**: Once the user confirms, generate code based on the Product Doc.
   Write files to the workspace directory.

5. **Refine**: When the user requests changes:
   - First update the relevant section(s) of PRODUCT.md (not the whole doc).
   - Output a brief summary (1-3 sentences) of what changed in the doc.
   - For **minor changes** (color, text, spacing, copy tweaks, small layout
     adjustments): immediately proceed to update the code in the same turn.
     Do NOT wait for confirmation.
   - For **major changes** (new sections, structural redesign, significant
     feature additions — the kind that would normally trigger a new round of
     interview questions): output the summary and ask in plain text whether
     to proceed, then stop and wait. Do NOT use `ask_user` for this — just
     write it as normal text.

## Rules

- NEVER generate code without a PRODUCT.md. Always create the doc first.
- NEVER create PRODUCT.md without asking the user at least one round of
  clarifying questions first via `ask_user`.
- When updating PRODUCT.md, only update the affected section(s), not the
  entire document. Use the edit_file tool for surgical updates.
- ALWAYS briefly summarize what was created or changed in the Product Doc
  before generating or updating code. Keep it concise (1-4 sentences).
- The Product Doc is the contract. Code must match the doc.
- Use `ask_user` ONLY for interview questions (gathering requirements).
  NEVER use `ask_user` for generation confirmation — use plain text instead.
"""


class App:
    """Main application facade."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config.load()
        self.console = Console()
        self.user_io = CLIUserIO(self.console._console)
        self.prompt = Prompt(
            history_file=self.config.data_dir / "history"
        )
        self.store = ProjectStore(self.config.data_dir)
        self.project: Project | None = None
        self.engine: Engine | None = None
        self._streaming_started = False

    def _create_engine(self, workspace: Path) -> Engine:
        agent_cfg = self.config.agents.get("main", AgentConfig())
        agent_cfg.system_prompt = (
            f"{SYSTEM_PROMPT}\n"
            f"## Workspace\n"
            f"Your working directory is: {workspace}\n"
            f"All file operations resolve relative paths against this directory.\n"
            f"Shell commands execute with this directory as cwd.\n"
            f"Write all generated code and files inside this workspace.\n"
        )
        engine = Engine(
            config=self.config,
            agent_config=agent_cfg,
            workspace=str(workspace),
            on_text_delta=self._on_text_delta,
            on_llm_retry=self._on_llm_retry,
            on_tool_call=self._on_tool_call,
            on_tool_result=self._on_tool_result,
            on_tool_progress=self._on_tool_progress,
            on_sub_agent_start=self._on_sub_agent_start,
            on_sub_agent_end=self._on_sub_agent_end,
            user_io=self.user_io,
        )
        engine.setup()
        return engine

    async def run(self, resume_project: str | None = None):
        """Main interactive loop."""
        if not self.config.models:
            if not run_setup(self.config):
                self.console.print_error(
                    "No models configured. Run 'ic' again or edit ~/.ic/config.toml"
                )
                return
            self.config = Config.load()

        # Create or resume project
        if resume_project:
            self.project = self.store.get(resume_project)
            if not self.project:
                self.console.print_error(f"Project '{resume_project}' not found")
                return
        else:
            self.project = self.store.create()

        workspace = self.store.workspace_dir(self.project.id)
        # Reload config with workspace for project-level overrides
        self.config = Config.load(workspace=workspace)
        self.config._ensure_agents()
        self.engine = self._create_engine(workspace)

        # Load existing context if resuming
        if resume_project:
            ctx_path = self.store.context_path(self.project.id)
            self.engine.context = Context.load(
                ctx_path, system_prompt=self.engine.agent_config.system_prompt
            )
            # Restore engine state (cost, usage, snapshots)
            state_path = self.store.project_dir(self.project.id) / "engine_state.json"
            self.engine.load_state(state_path)
            self.console.print_info(f"Resumed project: {self.project.id}")

        model_name = self.config.get_model(self.engine.agent_config.model).model
        self.console.print_welcome(model_name)
        self.console.print_info(f"Project: {self.project.id}  Workspace: {workspace}")

        # Main loop
        while True:
            try:
                user_input = await self.prompt.get_input("ic> ")
            except (EOFError, KeyboardInterrupt):
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            if user_input.startswith("/"):
                if not self._handle_command(user_input):
                    break
                continue

            self._streaming_started = False
            try:
                self.console.start_spinner("Thinking...")
                result = await self.engine.run_turn(user_input)
                self.console.stop_spinner()
                if self._streaming_started:
                    self.console.end_streaming()
                    self._streaming_started = False

                if result.usage:
                    self.console.print_usage(result.usage)

                # Save context and engine state
                ctx_path = self.store.context_path(self.project.id)
                self.engine.context.save(ctx_path)
                state_path = self.store.project_dir(self.project.id) / "engine_state.json"
                self.engine.save_state(state_path)
                self.store.update_timestamp(self.project)

            except KeyboardInterrupt:
                self.console.stop_spinner()
                if self._streaming_started:
                    self.console.end_streaming()
                self.engine.stop()
                # Show "Interrupted" in the separator so the user knows
                # they can type a new instruction (like Claude Code / Codex)
                self.prompt.set_status("Interrupted — tell the model what to do instead")
            except Exception as e:
                self.console.stop_spinner()
                if self._streaming_started:
                    self.console.end_streaming()
                self.console.print_error(str(e))

        self.console.print_info("Goodbye.")

    def _handle_command(self, cmd: str) -> bool:
        """Handle slash commands. Returns False to exit."""
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()

        if command in ("/quit", "/exit", "/q"):
            return False
        elif command == "/help":
            self.console.print_info(
                "Commands:\n"
                "  /quit, /exit, /q  - Exit\n"
                "  /clear            - Clear conversation\n"
                "  /undo             - Undo last turn\n"
                "  /rollback <n>     - Rollback last N turns\n"
                "  /branch <name>    - Save current state as named branch\n"
                "  /switch <name>    - Switch to a named branch\n"
                "  /checkpoints        - List conversation checkpoints\n"
                "  /revert <index>     - Revert to a specific checkpoint\n"
                "  /branches         - List saved branches\n"
                "  /doc              - Show product doc\n"
                "  /doc edit         - Open product doc in $EDITOR\n"
                "  /projects         - List projects\n"
                "  /workspace        - Show workspace path\n"
                "  /model            - Show current model\n"
                "  /model <name>     - Switch model\n"
                "  /model add        - Add a new model\n"
                "  /model list       - List all models\n"
                "  /usage            - Show token usage\n"
                "  /config           - Show config file path\n"
                "  /help             - Show this help"
            )
        elif command == "/clear":
            if self.engine:
                self.engine.context = Context(
                    system_prompt=self.engine.agent_config.system_prompt
                )
            self.console.print_info("Conversation cleared.")
        elif command == "/projects":
            projects = self.store.list_projects()
            if not projects:
                self.console.print_info("No projects.")
            else:
                for p in projects:
                    active = " *" if self.project and p.id == self.project.id else ""
                    self.console.print_info(f"  {p.id}  {p.title}  ({p.updated_at[:16]}){active}")
        elif command == "/workspace":
            if self.project:
                ws = self.store.workspace_dir(self.project.id)
                self.console.print_info(f"Workspace: {ws}")
        elif command == "/doc":
            self._handle_doc_command(parts[1].strip() if len(parts) > 1 else "")
        elif command == "/model":
            if len(parts) > 1:
                sub = parts[1].strip()
                if sub == "add":
                    self._add_model_interactive()
                elif sub == "list":
                    for name, m in self.config.models.items():
                        active = " *" if name == self.engine.agent_config.model else ""
                        url = f" @ {m.base_url}" if m.base_url else ""
                        alias = f" (-> {m.model})" if m.model != m.name else ""
                        self.console.print_info(f"  {name}{alias}{url}{active}")
                elif sub in self.config.models:
                    self.engine.agent_config.model = sub
                    self.engine.setup()
                    display_name = self.config.get_model(sub).model
                    self.console.print_welcome(display_name)
                else:
                    self.console.print_error(
                        f"Unknown model: {sub}. Use '/model list' to see available."
                    )
            else:
                current = self.engine.agent_config.model
                self.console.print_info(
                    f"Current: {current}\n"
                    f"Use '/model list' to see all, '/model <name>' to switch"
                )
        elif command == "/undo":
            if self.engine and self.engine.context.undo():
                self.console.print_info("Undid last turn.")
            else:
                self.console.print_info("Nothing to undo.")
        elif command == "/rollback":
            n = 1
            if len(parts) > 1:
                try:
                    n = int(parts[1].strip())
                except ValueError:
                    self.console.print_error("Usage: /rollback <number>")
                    return True
            if self.engine:
                removed = self.engine.context.rollback(n)
                self.console.print_info(f"Rolled back {removed} turn(s).")
        elif command == "/branch":
            if len(parts) < 2 or not parts[1].strip():
                self.console.print_error("Usage: /branch <name>")
            elif self.engine:
                name = parts[1].strip()
                self.engine.context.fork(name)
                self.console.print_info(f"Branch '{name}' saved.")
        elif command == "/switch":
            if len(parts) < 2 or not parts[1].strip():
                self.console.print_error("Usage: /switch <name>")
            elif self.engine:
                name = parts[1].strip()
                if self.engine.context.switch_branch(name):
                    self.console.print_info(f"Switched to branch '{name}'.")
                else:
                    available = ", ".join(self.engine.context.list_branches()) or "none"
                    self.console.print_error(f"Branch '{name}' not found. Available: {available}")
        elif command == "/branches":
            if self.engine:
                branches = self.engine.context.list_branches()
                if branches:
                    for b in branches:
                        self.console.print_info(f"  {b}")
                else:
                    self.console.print_info("No branches saved. Use /branch <name> to create one.")
        elif command == "/checkpoints":
            if self.engine:
                cps = self.engine.context.list_checkpoints()
                if cps:
                    for cp in cps:
                        self.console.print_info(
                            f"  [{cp['index']}] {cp['label'] or '(unlabeled)'}  "
                            f"— {cp['messages']} msgs, ~{cp['tokens']} tokens"
                        )
                else:
                    self.console.print_info("No checkpoints yet.")
        elif command == "/revert":
            if len(parts) < 2 or not parts[1].strip():
                self.console.print_error("Usage: /revert <index>")
            elif self.engine:
                try:
                    idx = int(parts[1].strip())
                except ValueError:
                    self.console.print_error("Usage: /revert <index> (must be a number)")
                    return True
                if self.engine.context.revert_to(idx):
                    self.console.print_info(
                        f"Reverted to checkpoint [{idx}]. "
                        f"Current state saved as branch 'pre-revert' (use /switch pre-revert to undo)."
                    )
                else:
                    count = len(self.engine.context._snapshots)
                    self.console.print_error(
                        f"Invalid index: {idx}. "
                        f"Available range: 0–{count - 1}" if count else f"Invalid index: {idx}. No checkpoints available."
                    )
        elif command == "/usage":
            if self.engine:
                self.console.print_usage(self.engine._total_usage)
        elif command == "/config":
            self.console.print_info(f"Config: {self.config.config_path}")
        else:
            self.console.print_error(f"Unknown command: {command}")
        return True

    def _add_model_interactive(self):
        try:
            model = input("  Model ID (e.g. gpt-4o, deepseek-chat): ").strip()
            if not model:
                return
            api_key = input("  API Key: ").strip()
            if not api_key:
                self.console.print_error("API key is required.")
                return
            base_url = input("  Base URL (Enter for OpenAI default): ").strip()
            timeout_input = input("  Timeout seconds [120]: ").strip()
            timeout = self.config._parse_positive_float(timeout_input, 120.0)
            name = input(f"  Short name [{model}]: ").strip() or model
            self.config.save_model(name, api_key, base_url, model, timeout=timeout)
            self.console.print_info(f"Added: {name}. Use '/model {name}' to switch.")
        except (EOFError, KeyboardInterrupt):
            pass

    def _handle_doc_command(self, sub: str):
        """Handle /doc commands."""
        if not self.project:
            self.console.print_error("No active project.")
            return

        doc_path = self.store.workspace_dir(self.project.id) / "PRODUCT.md"

        if sub == "edit":
            editor = os.environ.get("EDITOR", "vim")
            if not doc_path.exists():
                doc = ProductDoc.create_empty(self.project.title)
                doc.save(doc_path)
            os.system(f'{editor} "{doc_path}"')
        elif sub == "path":
            self.console.print_info(str(doc_path))
        else:
            # Show doc content
            doc = ProductDoc.load(doc_path)
            if doc:
                from rich.markdown import Markdown
                self.console._console.print(Markdown(doc.to_markdown()))
            else:
                self.console.print_info(
                    f"No PRODUCT.md yet. The agent will create one when you describe what to build."
                )

    # -- Callbacks --

    async def _on_text_delta(self, delta: str):
        if not self._streaming_started:
            self.console.stop_spinner()
            self.console.start_streaming()
            self._streaming_started = True
        self.console.stream_text(delta)

    async def _on_llm_retry(self, next_attempt: int, max_attempts: int, reason: str):
        if self._streaming_started:
            self.console.end_streaming()
            self._streaming_started = False
        self.console.stop_spinner()
        short_reason = reason.splitlines()[0].strip()
        if len(short_reason) > 140:
            short_reason = short_reason[:137] + "..."
        self.console.print_info(
            f"LLM retry {next_attempt}/{max_attempts}: {short_reason}"
        )
        self.console.start_spinner("Thinking...")

    async def _on_tool_call(self, name: str, tc: dict):
        self.console.stop_spinner()
        if self._streaming_started:
            self.console.end_streaming()
            self._streaming_started = False
        # ask_user renders its own UI via CLIUserIO, skip display
        if name == "ask_user":
            return
        # think is internal reasoning — keep spinner, don't show in feed
        if name == "think":
            self.console.start_spinner("Thinking...")
            return
        args = tc.get("arguments", "{}")
        try:
            parsed = json.loads(args) if isinstance(args, str) else args
        except Exception:
            parsed = {"raw": args}
        self.console.print_tool_call(name, parsed)
        # Show spinner with tool context while executing
        from ic.ui.console import _tool_call_summary
        summary = _tool_call_summary(name, parsed)
        self.console.start_spinner(summary + "...")

    async def _on_tool_result(self, name: str, result: str):
        self.console.stop_spinner()
        # ask_user already showed its UI, just show a brief summary
        if name == "ask_user":
            lines = result.strip().split("\n")
            count = sum(1 for l in lines if l.startswith("Q:"))
            self.console.print_info(f"  ({count} question(s) answered)")
            self.console.start_spinner("Thinking...")
            return
        # think is internal reasoning — silent
        if name == "think":
            self.console.start_spinner("Thinking...")
            return
        self.console.print_tool_result(name, result)
        self.console.start_spinner("Thinking...")

    async def _on_tool_progress(self, tool_name: str, message: str, percent: int | None):
        self.console.print_tool_progress(tool_name, message, percent)

    async def _on_sub_agent_start(self, task: str):
        self.console.print_sub_agent_start(task)

    async def _on_sub_agent_end(self, result: str):
        self.console.print_sub_agent_end(result)
