"""EngineOrchestrator — the primary orchestrator for the web backend.

Uses the agent Engine under the hood, exposing a ``stream_responses()``
async-generator interface consumed by the chat API.
"""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Optional, Sequence

from sqlalchemy.orm import Session as DbSession

from ..schemas.orchestrator_response import OrchestratorResponse
from ..config import get_settings
from ..db.models import Session as SessionModel
from ..events.emitter import EventEmitter
from ..events.models import DoneEvent, ErrorEvent, run_lifecycle_event
from ..events.types import EventType
from ..schemas.run import RunPhase, RunStatus, normalize_execution_mode
from ..services.message import MessageService
from ..services.run import RunNotFoundError, RunService, RunStateConflictError

from .config_bridge import backend_settings_to_agent_config
from .db_tools import DBEditFile, DBMultiEditFile, DBWriteFile
from .deferred_buffer import DeferredPersistenceBuffer
from .event_bridge import EventBridge
from .prompts import build_system_prompt
from .registry import engine_registry
from .web_user_io import WebUserIO

logger = logging.getLogger(__name__)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _waiting_reason_from_questions(questions: list[dict[str, Any]]) -> str:
    if questions:
        first = questions[0]
        for key in ("question", "title", "message"):
            value = first.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "Waiting for user input"


class EngineOrchestrator:
    """Primary orchestrator — wraps the agent Engine for web backend use."""

    def __init__(
        self,
        db: DbSession,
        session: SessionModel,
        event_emitter: EventEmitter | None = None,
    ) -> None:
        self.db = db
        self.session = session
        self.settings = get_settings()
        self.event_emitter = event_emitter or EventEmitter(
            session_id=session.id
        )
        self._web_user_io = WebUserIO(
            self.event_emitter,
            session.id,
            on_waiting_input=self._mark_run_waiting_input,
            on_answer_resolved=self._mark_run_resumed,
        )
        self._engine = None
        self.thread_id: str | None = None
        self._execution_mode = "agent"
        self._bridge: EventBridge | None = None
        self._sub_agent_sessions: list[DbSession] = []
        self._deferred_buffer = DeferredPersistenceBuffer()

    @property
    def has_pending_question(self) -> bool:
        return self._web_user_io.has_pending

    def resolve_answer(self, answer_payload: Any) -> bool:
        """Route a user answer to the pending ask_user call."""
        return self._web_user_io.resolve_answer(answer_payload)

    def resolve_shell_approval(self, approval_id: str, approved: bool) -> bool:
        """Route a shell approval response to the active event bridge."""
        if self._bridge is None:
            return False
        return self._bridge.resolve_shell_approval(approval_id, approved)

    def _mark_run_waiting_input(self, batch_id: str, questions: list[dict[str, Any]]) -> None:
        run_id = self.event_emitter.run_id
        if not run_id:
            return

        run_service = RunService(self.db)
        try:
            run = run_service.get_run(run_id)
        except RunNotFoundError:
            logger.warning("Cannot mark missing run %s as waiting_input", run_id)
            return

        if run.status == RunStatus.WAITING_INPUT.value:
            return
        if run.status != RunStatus.RUNNING.value:
            logger.info("Skip waiting_input transition for run %s in state %s", run_id, run.status)
            return

        waiting_reason = _waiting_reason_from_questions(questions)
        waiting_at = _utc_iso()
        payload = {
            "batch_id": batch_id,
            "waiting_reason": waiting_reason,
            "questions": questions,
        }
        try:
            run_service.persist_run_phase(
                run_id,
                RunPhase.IMPLEMENT,
                status=RunStatus.WAITING_INPUT,
                waiting_reason=waiting_reason,
                waiting_at=waiting_at,
                result=payload,
            )
            run_service.heartbeat_run(
                run_id,
                phase=RunPhase.IMPLEMENT,
                status=RunStatus.WAITING_INPUT,
                step="waiting_input",
            )
            run_service.persist_run_state(
                run_id,
                RunStatus.WAITING_INPUT.value,
                latest_error={
                    "waiting_reason": waiting_reason,
                    "batch_id": batch_id,
                },
            )
            run = run_service.get_run(run_id)
            self._record_coordinator_phase(
                run,
                phase=RunPhase.IMPLEMENT.value,
                status=RunStatus.WAITING_INPUT.value,
                waiting_reason=waiting_reason,
                waiting_at=waiting_at,
                output=payload,
            )
            self.event_emitter.emit(
                run_lifecycle_event(
                    EventType.RUN_WAITING_INPUT,
                    phase=RunPhase.IMPLEMENT.value,
                    status=RunStatus.WAITING_INPUT.value,
                    waiting_reason=waiting_reason,
                    batch_id=batch_id,
                )
            )
            self.db.commit()
        except RunStateConflictError:
            logger.exception("Invalid waiting_input transition for run %s", run_id)

    def _mark_run_resumed(self, batch_id: str, answer_payload: Any) -> None:
        run_id = self.event_emitter.run_id
        if not run_id:
            return

        run_service = RunService(self.db)
        try:
            run = run_service.get_run(run_id)
        except RunNotFoundError:
            logger.warning("Cannot resume missing run %s", run_id)
            return

        if run.status == RunStatus.WAITING_INPUT.value:
            try:
                run_service.resume_run(
                    run_id,
                    {
                        "source": "ask_user",
                        "batch_id": batch_id,
                        "answers": answer_payload,
                    },
                )
            except RunStateConflictError:
                logger.exception("Invalid resume transition for run %s", run_id)
                return
        elif run.status != RunStatus.RUNNING.value:
            logger.info("Skip resume transition for run %s in state %s", run_id, run.status)
            return

        try:
            run_service.persist_run_phase(
                run_id,
                RunPhase.IMPLEMENT,
                status=RunStatus.RUNNING,
                resumed_at=_utc_iso(),
            )
            run_service.heartbeat_run(
                run_id,
                phase=RunPhase.IMPLEMENT,
                status=RunStatus.RUNNING,
                step="answer_received",
            )
            run = run_service.get_run(run_id)
            self._record_coordinator_phase(
                run,
                phase=RunPhase.IMPLEMENT.value,
                status=RunStatus.RUNNING.value,
                resumed_at=_utc_iso(),
                output={
                    "source": "ask_user",
                    "batch_id": batch_id,
                    "answers": answer_payload,
                },
            )
            self.event_emitter.emit(
                run_lifecycle_event(
                    EventType.RUN_RESUMED,
                    phase=RunPhase.IMPLEMENT.value,
                    status=RunStatus.RUNNING.value,
                    batch_id=batch_id,
                )
            )
            self.db.commit()
        except RunStateConflictError:
            logger.exception("Failed to persist resumed phase for run %s", run_id)

    def _record_coordinator_phase(
        self,
        run,
        *,
        phase: str,
        status: str,
        **metadata: Any,
    ) -> None:
        metrics = dict(run.metrics) if isinstance(run.metrics, dict) else {}
        coordinator = dict(metrics.get("coordinator") or {})
        phase_history = list(coordinator.get("phase_history") or [])
        entry = {
            "phase": phase,
            "status": status,
            **{key: value for key, value in metadata.items() if value is not None},
        }
        if (
            phase_history
            and phase_history[-1].get("phase") == phase
            and phase_history[-1].get("status") != RunStatus.COMPLETED.value
        ):
            phase_history[-1] = {**phase_history[-1], **entry}
        else:
            phase_history.append(entry)
        coordinator["current_phase"] = phase
        coordinator["phase_history"] = phase_history
        coordinator["fix_attempts"] = int(coordinator.get("fix_attempts") or 0)
        coordinator["artifacts"] = dict(coordinator.get("artifacts") or {})
        metrics["coordinator"] = coordinator
        run.metrics = metrics
        self.db.add(run)

    def _create_sub_agent_tools(self, sub_engine: Any) -> list:
        """Tool factory for sub-agents: returns DB-backed WriteFile/EditFile.

        Each sub-agent gets its own DbSession for concurrency safety.
        """
        from ..db.database import get_database

        sub_db = get_database().session()
        self._sub_agent_sessions.append(sub_db)

        ws = Path(sub_engine.workspace) if sub_engine.workspace else None
        return [
            DBWriteFile(
                workspace=ws,
                db_session=sub_db,
                session_id=self.session.id,
                emitter=self.event_emitter,
                engine=sub_engine,
                deferred_buffer=self._deferred_buffer,
                execution_mode=self._execution_mode,
            ),
            DBEditFile(
                workspace=ws,
                db_session=sub_db,
                session_id=self.session.id,
                emitter=self.event_emitter,
                engine=sub_engine,
                deferred_buffer=self._deferred_buffer,
                execution_mode=self._execution_mode,
            ),
        ]

    def _setup_engine(self, workspace: str) -> None:
        """Create and configure the Engine instance."""
        from ic.config import AgentConfig
        from ic.soul.context_injector import ContextConfig
        from ic.soul.engine import Engine
        from ic.soul.skills import SkillLoader
        from ic.tools.skill import ExecuteSkill

        config = backend_settings_to_agent_config(self.settings)
        bridge = EventBridge(self.event_emitter, self.session.id, execution_mode=self._execution_mode)

        # Load existing session state for the system prompt
        product_doc_content = self._load_product_doc_content()
        pages = self._load_pages_summary()
        memory_context = self._load_memory_context()

        system_prompt = build_system_prompt(
            workspace=workspace,
            product_doc_content=product_doc_content,
            pages=pages,
            memory_context=memory_context,
            execution_mode=self._execution_mode,
        )

        ws_path = Path(workspace)

        # Setup skills loader
        skills_dir = Path(self.settings.skills_dir) if self.settings.skills_dir else None
        skill_loader = SkillLoader(skills_dir)

        # Build tool list — use DB-backed file tools instead of plain ones
        tool_paths = [
            "ic.tools.file:ReadFile",
            "ic.tools.file:GlobFiles",
            "ic.tools.file:GrepFiles",
            "ic.tools.think:Think",
            "ic.tools.todo:Todo",
            "ic.tools.ask:AskUser",
            "ic.tools.subagent:CreateSubAgent",
            "ic.tools.subagent:CreateParallelSubAgents",
        ]
        if self._execution_mode != "plan":
            tool_paths.insert(3, "ic.tools.shell:Shell")

        agent_cfg = AgentConfig(
            name="web-engine",
            system_prompt=system_prompt,
            model=config.default_model,
            tools=tool_paths,
            max_turns=50,
        )

        # Context injection config - optimized for isolated web sessions
        context_config = ContextConfig(
            include_product_doc=True,      # Auto-discover product-doc.md
            include_git_status=False,      # Not useful for isolated sessions
            include_directory_tree=True,   # Show available files
            directory_max_files=30,        # Limit for token efficiency
            use_flat_file_list=True,       # Flatter format = fewer tokens
        )

        engine = Engine(
            config=config,
            agent_config=agent_cfg,
            workspace=workspace,
            user_io=self._web_user_io,
            on_text_delta=bridge.on_text_delta,
            on_tool_call=bridge.on_tool_call,
            on_tool_result=bridge.on_tool_result,
            on_tool_progress=bridge.on_tool_progress,
            on_sub_agent_start=bridge.on_sub_agent_start,
            on_sub_agent_end=bridge.on_sub_agent_end,
            on_cost_update=bridge.on_cost_update,
            on_before_shell_execute=bridge.on_before_shell_execute,
            context_config=context_config,
            on_context_compacted=bridge.on_context_compacted,
            on_plan_update=bridge.on_plan_update,
            project_state_provider=lambda: self._get_project_state(),
        )
        engine.setup()

        # Wire sub-agent tool factory for DB-backed file tools
        engine.sub_agent_tool_factory = self._create_sub_agent_tools

        # Add the skill tool
        skill_tool = ExecuteSkill(skill_loader=skill_loader, workspace=ws_path)
        skill_tool._update_description()  # Update with available skills
        engine.toolset.add(skill_tool)

        # Add MultiEditFile tool — use DB-backed version with deferred buffer
        from ic.tools.file import MultiEditFile
        db_multi_edit = DBMultiEditFile(
            workspace=ws_path,
            db_session=self.db,
            session_id=self.session.id,
            emitter=self.event_emitter,
            deferred_buffer=self._deferred_buffer,
            execution_mode=self._execution_mode,
        )
        engine.toolset.add(db_multi_edit)

        # Replace the plain WriteFile and EditFile with DB-backed versions
        db_write = DBWriteFile(
            workspace=ws_path,
            db_session=self.db,
            session_id=self.session.id,
            emitter=self.event_emitter,
            engine=engine,
            deferred_buffer=self._deferred_buffer,
            execution_mode=self._execution_mode,
        )
        db_edit = DBEditFile(
            workspace=ws_path,
            db_session=self.db,
            session_id=self.session.id,
            emitter=self.event_emitter,
            engine=engine,
            deferred_buffer=self._deferred_buffer,
            execution_mode=self._execution_mode,
        )
        engine.toolset.add(db_write)
        engine.toolset.add(db_edit)

        # Add web tools (search and fetch)
        from ic.tools.web import WebSearch, WebFetch
        engine.toolset.add(WebSearch())
        engine.toolset.add(WebFetch())

        # Connect background task lifecycle events to EventBridge
        shell_tool = engine.toolset.get("shell")
        if shell_tool and hasattr(shell_tool, "task_manager"):
            tm = shell_tool.task_manager
            tm.on_task_started = bridge.emit_bg_task_started
            tm.on_task_completed = bridge.emit_bg_task_completed
            tm.on_task_failed = bridge.emit_bg_task_failed

        self._engine = engine
        self._bridge = bridge

    def _load_product_doc_content(self) -> Optional[str]:
        from ..services.product_doc import ProductDocService

        try:
            doc = ProductDocService(self.db).get_by_session_id(self.session.id)
            return doc.content if doc else None
        except Exception:
            return None

    def _load_pages_summary(self) -> Optional[list[dict[str, Any]]]:
        from ..services.page import PageService

        try:
            pages = PageService(self.db).list_by_session(self.session.id)
            if not pages:
                return None
            return [{"slug": p.slug, "title": p.title} for p in pages]
        except Exception:
            return None

    def _get_project_state(self) -> dict[str, Any]:
        """Build project state dict for context injection after compaction."""
        from ..services.build_payload import get_project_state

        try:
            return get_project_state(self.db, self.session.id)
        except Exception:
            return {}

    def _load_memory_context(self) -> Optional[str]:
        """Load project memory context for system prompt injection."""
        from ..services.memory import ProjectMemoryService

        try:
            return ProjectMemoryService(self.db).build_memory_context(self.session.id) or None
        except Exception:
            return None

    def _save_design_decisions(self, tool_calls: list[dict]) -> None:
        """Extract and save design decisions from tool calls."""
        from ..services.memory import ProjectMemoryService

        try:
            ProjectMemoryService(self.db).extract_and_save_decisions(
                self.session.id, tool_calls
            )
        except Exception:
            logger.debug("Failed to save design decisions")

    def _read_mentioned_file(self, workspace: str, file_path: str) -> Optional[str]:
        """Read a mentioned file from the workspace or DB pages."""
        # Try workspace filesystem first
        full_path = Path(workspace) / file_path
        if full_path.exists() and full_path.is_file():
            try:
                return full_path.read_text(encoding="utf-8")
            except Exception:
                return None

        # Try DB pages (slug-based lookup)
        from ..services.page import PageService
        slug = Path(file_path).stem
        try:
            page = PageService(self.db).get_by_slug(self.session.id, slug)
            if page and page.versions:
                latest = max(page.versions, key=lambda v: v.version_number)
                return latest.html_content
        except Exception:
            pass

        return None

    async def stream_responses(
        self,
        *,
        user_message: str,
        output_dir: str,
        history: Sequence[dict] | None = None,
        trigger_interview: bool = True,
        generate_now: bool = False,
        style_reference: Optional[dict] = None,
        target_pages: Optional[list[str]] = None,
        resume: Optional[dict] = None,
        image_refs: Optional[list[dict]] = None,
        mentioned_files: Optional[list[str]] = None,
        execution_mode: Optional[str] = None,
        approval_mode: str = "agent",
    ) -> AsyncGenerator[OrchestratorResponse, None]:
        """Run the engine and yield OrchestratorResponse objects."""
        workspace = self._resolve_workspace(output_dir)
        self._execution_mode = normalize_execution_mode(
            execution_mode if execution_mode is not None else approval_mode
        )

        try:
            self._setup_engine(workspace)
        except Exception as exc:
            logger.exception("Failed to set up engine")
            self.event_emitter.emit(
                ErrorEvent(
                    session_id=self.session.id,
                    message=f"Engine setup failed: {exc}",
                )
            )
            yield OrchestratorResponse(
                session_id=self.session.id,
                phase="error",
                message=f"Engine setup failed: {exc}",
                is_complete=True,
                action="error",
            )
            return

        engine_registry.register(self.session.id, self)

        try:
            # Yield an initial "thinking" response
            yield OrchestratorResponse(
                session_id=self.session.id,
                phase="engine_running",
                message="",
                is_complete=False,
                action="engine_start",
            )

            # Handle image references — enrich user_message with intent labels
            # and pass image URLs to the engine for multi-modal context
            images_for_engine: list[dict] | None = None
            if image_refs:
                intent_parts = []
                images_for_engine = []
                for ref in image_refs:
                    intent = ref.get("intent", "asset")
                    url = ref.get("url", "")
                    desc = ref.get("description", "")
                    intent_parts.append(
                        f"[Attached image — intent: {intent}]"
                        + (f": {desc}" if desc else "")
                    )
                    if url:
                        images_for_engine.append({"url": url})
                if intent_parts:
                    user_message = "\n".join(intent_parts) + "\n\n" + user_message
                if not images_for_engine:
                    images_for_engine = None

            # Inject mentioned file contents into user message
            if mentioned_files:
                file_context_parts = []
                for fpath in mentioned_files[:5]:  # Limit to 5 files
                    content = self._read_mentioned_file(workspace, fpath)
                    if content is not None:
                        file_context_parts.append(
                            f"<referenced_file path=\"{fpath}\">\n{content[:8000]}\n</referenced_file>"
                        )
                if file_context_parts:
                    user_message = "\n".join(file_context_parts) + "\n\n" + user_message

            if not trigger_interview:
                user_message = (
                    "<interview_mode>\n"
                    "Interview has already been completed or explicitly skipped.\n"
                    "Do not ask additional clarifying questions with ask_user.\n"
                    "Proceed directly with PRODUCT.md updates and generation/refinement.\n"
                    "</interview_mode>\n\n"
                    + user_message
                )

            result = await self._engine.run_turn(user_message, images=images_for_engine)

            # Flush deferred writes — one version per file for this turn
            if self._execution_mode == "plan":
                self._deferred_buffer.clear()
            else:
                self._deferred_buffer.flush(self.db, self.session.id, self.event_emitter)

            # Emit file change events
            if self._engine.file_changes:
                self._bridge.emit_files_changed(self._engine.file_changes)

            # Save design decisions from tool calls to project memory
            if result.tool_calls:
                self._save_design_decisions(result.tool_calls)

            # Sync React workspace pages to DB so preview/build/versioning work
            synced_slugs = self._sync_workspace_react_pages(workspace)

            # Build final response
            text = result.text or self._bridge.get_accumulated_text()
            affected = self._get_affected_pages()
            active_slug = affected[0] if affected else None
            has_product_doc = self._load_product_doc_content() is not None

            action = self._determine_action(result, affected, synced_slugs)

            self._bridge.emit_token_usage(
                result.usage,
                cost_usd=result.cost.get("total_cost_usd", 0.0),
            )

            # Persist the assistant message directly — text was already
            # streamed to the frontend via TextDeltaEvents so we yield
            # an empty message to avoid _stream_message_payload re-chunking.
            if text:
                try:
                    MessageService(self.db).add_message(
                        self.session.id, "assistant", text,
                        thread_id=self.thread_id,
                    )
                    self.db.commit()
                except Exception:
                    logger.exception("Failed to persist engine assistant message")

            self.event_emitter.emit(
                DoneEvent(
                    session_id=self.session.id,
                    summary=text[:200] if text else None,
                )
            )

            yield OrchestratorResponse(
                session_id=self.session.id,
                phase="complete",
                message="",
                is_complete=True,
                action=action,
                product_doc_updated=has_product_doc,
                affected_pages=affected,
                active_page_slug=active_slug,
            )

        except Exception as exc:
            logger.exception("Engine run failed")
            # Flush deferred writes to preserve partial work
            try:
                if self._execution_mode == "plan":
                    self._deferred_buffer.clear()
                else:
                    self._deferred_buffer.flush(self.db, self.session.id, self.event_emitter)
            except Exception:
                logger.exception("Deferred buffer flush failed during error handling")
            # Preserve React workspace files written before the error.
            try:
                synced_slugs = self._sync_workspace_react_pages(workspace)
                affected = self._get_affected_pages()
            except Exception:
                synced_slugs = []
                affected = []

            # Update session status to partial instead of leaving as pending
            try:
                self.session.build_status = "partial"
                self.db.commit()
            except Exception:
                logger.exception("Failed to update session build status")

            self.event_emitter.emit(
                ErrorEvent(
                    session_id=self.session.id,
                    message=str(exc),
                )
            )

            # Return partial_complete instead of error if we have affected pages
            action = "partial_complete" if affected else "error"
            yield OrchestratorResponse(
                session_id=self.session.id,
                phase="partial" if affected else "error",
                message=f"Engine error: {exc}",
                is_complete=True,
                action=action,
                affected_pages=affected,
            )
        finally:
            engine_registry.unregister(self.session.id)
            # Close sub-agent DB sessions
            for sub_db in self._sub_agent_sessions:
                try:
                    sub_db.close()
                except Exception:
                    pass
            self._sub_agent_sessions.clear()

    def _resolve_workspace(self, output_dir: str) -> str:
        """Get or create a workspace directory for this session."""
        base = Path(output_dir).expanduser()
        workspace = base / self.session.id
        workspace.mkdir(parents=True, exist_ok=True)
        return str(workspace)

    def _get_affected_pages(self) -> list[str]:
        """Return slugs of pages that were created/modified during this turn."""
        from ..services.page import PageService

        try:
            pages = PageService(self.db).list_by_session(self.session.id)
            return [p.slug for p in pages]
        except Exception:
            return []

    def _sync_workspace_react_pages(self, workspace: str) -> list[str]:
        """Discover React pages from workspace source and sync them to the DB.

        Scans ``src/pages/*.tsx`` and ensures a ``Page`` + ``PageVersion`` record
        exists for each so that preview, versioning, and build discovery work.
        """
        from ..services.page import PageService
        from ..services.page_version import PageVersionService

        ws = Path(workspace)
        pages_dir = ws / "src" / "pages"
        slugs: list[str] = []

        if pages_dir.is_dir():
            for path in sorted(pages_dir.glob("*.tsx")):
                if path.name.startswith("_"):
                    continue
                slugs.append(path.stem)

        if not slugs and (ws / "src" / "App.tsx").is_file():
            slugs.append("index")

        if not slugs:
            return []

        page_service = PageService(self.db, event_emitter=self.event_emitter)
        page_version_service = PageVersionService(self.db, event_emitter=self.event_emitter)
        existing = {p.slug: p for p in page_service.list_by_session(self.session.id)}
        synced: list[str] = []

        for idx, slug in enumerate(slugs):
            title = slug.replace("-", " ").title()
            if slug in existing:
                page = existing[slug]
                if page.title != title:
                    page_service.update(page.id, title=title)
            else:
                page = page_service.create(
                    session_id=self.session.id,
                    title=title,
                    slug=slug,
                    order_index=idx,
                )

            # Ensure a PageVersion record exists so preview API has something to return
            current = page_version_service.get_current(page.id)
            if current is None:
                page_version_service.create(
                    page_id=page.id,
                    html="",
                    description="React source page",
                    fallback_used=True,
                    fallback_excerpt="Page version created from React workspace source",
                )
            synced.append(slug)

        self.db.commit()
        return synced

    def _determine_action(self, result: Any, affected_pages: list[str], synced_slugs: list[str] | None = None) -> str:
        """Determine the response action based on what the engine did."""
        tool_names = {tc.get("name", "") for tc in result.tool_calls}

        if "ask_user" in tool_names:
            return "refine_waiting"

        wrote_react_source = any(
            tc.get("name") == "write_file"
            and (
                "src/App.tsx" in str(tc.get("arguments", ""))
                or "src/main.tsx" in str(tc.get("arguments", ""))
                or "src/pages/" in str(tc.get("arguments", ""))
            )
            for tc in result.tool_calls
        )
        wrote_product_doc = any(
            tc.get("name") == "write_file"
            and "product" in str(tc.get("arguments", "")).lower()
            for tc in result.tool_calls
        )
        edited_react_source = any(
            tc.get("name") == "edit_file"
            and (
                "src/App.tsx" in str(tc.get("arguments", ""))
                or "src/main.tsx" in str(tc.get("arguments", ""))
                or "src/pages/" in str(tc.get("arguments", ""))
            )
            for tc in result.tool_calls
        )

        if wrote_react_source:
            return "pages_generated"
        if edited_react_source:
            return "page_refined"
        if "create_parallel_sub_agents" in tool_names or "create_sub_agent" in tool_names:
            # Sub-agents wrote files — check if pages exist in DB
            if affected_pages:
                return "pages_generated"
        if wrote_product_doc:
            edited_product_doc = any(
                tc.get("name") == "edit_file"
                and "product" in str(tc.get("arguments", "")).lower()
                for tc in result.tool_calls
            )
            return "product_doc_updated" if edited_product_doc else "product_doc_generated"

        # Fallback: workspace sync found orphaned HTML files
        if synced_slugs:
            return "pages_generated"

        # Fallback: DB has pages for this session even though no write_file/edit_file
        # was detected — the LLM may have used shell to write HTML directly
        if affected_pages:
            return "pages_generated"

        return "direct_reply"
