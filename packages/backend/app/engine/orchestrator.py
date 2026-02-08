"""EngineOrchestrator — drop-in replacement for AgentOrchestrator.

Uses the agent Engine under the hood while exposing the same
``stream_responses()`` async-generator interface so the chat API
can switch between the two via a feature flag.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any, AsyncGenerator, Optional, Sequence

from sqlalchemy.orm import Session as DbSession

from ..agents.orchestrator import OrchestratorResponse
from ..config import get_settings
from ..db.models import Session as SessionModel
from ..events.emitter import EventEmitter
from ..events.models import DoneEvent, ErrorEvent

from .config_bridge import backend_settings_to_agent_config
from .db_tools import DBEditFile, DBWriteFile
from .event_bridge import EventBridge
from .prompts import build_system_prompt
from .registry import engine_registry
from .web_user_io import WebUserIO

logger = logging.getLogger(__name__)


class EngineOrchestrator:
    """Wraps the agent Engine to match AgentOrchestrator's interface."""

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
            self.event_emitter, session.id
        )
        self._engine = None

    @property
    def has_pending_question(self) -> bool:
        return self._web_user_io.has_pending

    def resolve_answer(self, answer_payload: Any) -> bool:
        """Route a user answer to the pending ask_user call."""
        return self._web_user_io.resolve_answer(answer_payload)

    def _setup_engine(self, workspace: str) -> None:
        """Create and configure the Engine instance."""
        from ic.config import AgentConfig
        from ic.soul.engine import Engine

        config = backend_settings_to_agent_config(self.settings)
        bridge = EventBridge(self.event_emitter, self.session.id)

        # Load existing session state for the system prompt
        product_doc_content = self._load_product_doc_content()
        pages = self._load_pages_summary()

        system_prompt = build_system_prompt(
            workspace=workspace,
            product_doc_content=product_doc_content,
            pages=pages,
        )

        ws_path = Path(workspace)

        # Build tool list — use DB-backed file tools instead of plain ones
        tool_paths = [
            "ic.tools.file:ReadFile",
            "ic.tools.file:GlobFiles",
            "ic.tools.file:GrepFiles",
            "ic.tools.shell:Shell",
            "ic.tools.think:Think",
            "ic.tools.todo:Todo",
            "ic.tools.ask:AskUser",
            "ic.tools.subagent:CreateSubAgent",
        ]

        agent_cfg = AgentConfig(
            name="web-engine",
            system_prompt=system_prompt,
            model=config.default_model,
            tools=tool_paths,
            max_turns=50,
        )

        engine = Engine(
            config=config,
            agent_config=agent_cfg,
            workspace=workspace,
            user_io=self._web_user_io,
            on_text_delta=bridge.on_text_delta,
            on_tool_call=bridge.on_tool_call,
            on_tool_result=bridge.on_tool_result,
            on_sub_agent_start=bridge.on_sub_agent_start,
            on_sub_agent_end=bridge.on_sub_agent_end,
        )
        engine.setup()

        # Replace the plain WriteFile and EditFile with DB-backed versions
        db_write = DBWriteFile(
            workspace=ws_path,
            db_session=self.db,
            session_id=self.session.id,
            emitter=self.event_emitter,
        )
        db_edit = DBEditFile(
            workspace=ws_path,
            db_session=self.db,
            session_id=self.session.id,
            emitter=self.event_emitter,
        )
        engine.toolset.add(db_write)
        engine.toolset.add(db_edit)

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
    ) -> AsyncGenerator[OrchestratorResponse, None]:
        """Run the engine and yield OrchestratorResponse objects.

        This matches the AgentOrchestrator.stream_responses() interface.
        """
        workspace = self._resolve_workspace(output_dir)

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

            result = await self._engine.run_turn(user_message)

            # Build final response
            text = result.text or self._bridge.get_accumulated_text()
            affected = self._get_affected_pages()
            active_slug = affected[0] if affected else None
            has_product_doc = self._load_product_doc_content() is not None

            action = self._determine_action(result, affected)

            self._bridge.emit_token_usage(result.usage)

            self.event_emitter.emit(
                DoneEvent(
                    session_id=self.session.id,
                    summary=text[:200] if text else None,
                )
            )

            yield OrchestratorResponse(
                session_id=self.session.id,
                phase="complete",
                message=text,
                is_complete=True,
                action=action,
                product_doc_updated=has_product_doc,
                affected_pages=affected,
                active_page_slug=active_slug,
            )

        except Exception as exc:
            logger.exception("Engine run failed")
            self.event_emitter.emit(
                ErrorEvent(
                    session_id=self.session.id,
                    message=str(exc),
                )
            )
            yield OrchestratorResponse(
                session_id=self.session.id,
                phase="error",
                message=f"Engine error: {exc}",
                is_complete=True,
                action="error",
            )
        finally:
            engine_registry.unregister(self.session.id)

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

    def _determine_action(self, result: Any, affected_pages: list[str]) -> str:
        """Determine the response action based on what the engine did."""
        tool_names = {tc.get("name", "") for tc in result.tool_calls}

        if "ask_user" in tool_names:
            return "refine_waiting"

        wrote_html = any(
            tc.get("name") == "write_file"
            and str(tc.get("arguments", "")).endswith(".html")
            for tc in result.tool_calls
        )
        wrote_product_doc = any(
            tc.get("name") == "write_file"
            and "product" in str(tc.get("arguments", "")).lower()
            for tc in result.tool_calls
        )
        edited_html = any(
            tc.get("name") == "edit_file"
            and str(tc.get("arguments", "")).endswith(".html")
            for tc in result.tool_calls
        )

        if wrote_html:
            return "pages_generated"
        if edited_html:
            return "page_refined"
        if wrote_product_doc:
            return "product_doc_updated"

        return "direct_reply"
