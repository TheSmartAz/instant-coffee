from __future__ import annotations

import inspect
import logging
import uuid
from typing import Any, AsyncGenerator, Optional

from sqlalchemy.orm import Session as DbSession

from langgraph.types import Command

from ..utils.datetime import utcnow
from ..agents.orchestrator import OrchestratorResponse
from ..config import get_settings
from ..db.models import SessionRun
from ..db.models import Session as SessionModel
from ..events.emitter import EventEmitter
from ..events.models import (
    AgentEndEvent,
    AgentStartEvent,
    DoneEvent,
    ErrorEvent,
    EventType,
    interrupt_event,
    refine_waiting_event,
    workflow_event,
)
from ..services.run import RunCancelledError, RunService, RunStateConflictError
from ..services.state_store import StateStoreService
from .checkpointer import build_checkpointer
from .graph import create_generation_graph
from .state import GraphState

logger = logging.getLogger(__name__)


class LangGraphOrchestrator:
    def __init__(self, db: DbSession, session: SessionModel, event_emitter: EventEmitter | None = None) -> None:
        self.db = db
        self.session = session
        self.settings = get_settings()
        self.event_emitter = event_emitter
        self._checkpointer = build_checkpointer(self.settings)
        self._graph = create_generation_graph(event_emitter=self.event_emitter, checkpointer=self._checkpointer)

    def _emit(self, event: Any) -> None:
        if not self.event_emitter:
            return
        try:
            self.event_emitter.emit(event)
        except Exception:
            logger.exception("Failed to emit LangGraph event")

    def _graph_config(self) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": self.session.id}}

    @staticmethod
    def _parse_interrupt_payload(payload: Any) -> dict[str, Any]:
        if isinstance(payload, (list, tuple)) and payload:
            first = payload[0]
            if isinstance(first, dict) and "value" in first:
                value = first.get("value")
                if isinstance(value, dict):
                    return dict(value)
                return {"value": value}
            if hasattr(first, "value"):
                value = getattr(first, "value")
                if isinstance(value, dict):
                    return dict(value)
                return {"value": value}
        if isinstance(payload, dict):
            if "value" in payload and isinstance(payload.get("value"), dict):
                return dict(payload["value"])
            return dict(payload)
        return {"value": payload}

    @staticmethod
    def _normalize_stream_update(update: Any) -> Any:
        if isinstance(update, tuple) and len(update) == 2:
            mode, payload = update
            if mode == "updates":
                return payload
        return update

    def _emit_interrupt(self, payload: Any) -> None:
        if payload is None:
            return
        parsed = self._parse_interrupt_payload(payload)
        if parsed:
            self._emit(interrupt_event(parsed))
            if parsed.get("type") == "need_user_feedback":
                self._emit(refine_waiting_event(parsed))
        else:
            self._emit(interrupt_event({"value": payload}))

    @staticmethod
    def _merge_updates(current: dict | None, update: Any) -> dict:
        if current is None:
            current = {}
        if not isinstance(update, dict):
            return current
        for key, value in update.items():
            if key.startswith("__"):
                continue
            if isinstance(value, dict):
                current.update(value)
        return current

    async def _resolve_state(self, config: dict[str, Any], fallback: dict | None) -> dict:
        snapshot = None
        try:
            snapshot = self._graph.get_state(config)
            if inspect.isawaitable(snapshot):
                snapshot = await snapshot
        except Exception:
            logger.exception("Failed to read LangGraph state")
        if snapshot is not None:
            values = getattr(snapshot, "values", None)
            if isinstance(values, dict):
                return dict(values)
            if isinstance(snapshot, dict):
                maybe_values = snapshot.get("values")
                if isinstance(maybe_values, dict):
                    return dict(maybe_values)
                return dict(snapshot)
        return dict(fallback or {})

    @staticmethod
    def _strip_runtime_fields(state: dict) -> dict:
        for key in ("mcp_tools", "mcp_tool_handlers"):
            state.pop(key, None)
        return state

    def _build_initial_state(
        self,
        *,
        user_message: str,
        style_reference: Optional[dict],
        run_id: str,
    ) -> GraphState:
        assets: list[dict[str, Any]] = []
        if style_reference and isinstance(style_reference.get("images"), list):
            assets = list(style_reference.get("images") or [])

        return {
            "session_id": self.session.id,
            "user_input": user_message,
            "assets": assets,
            "mcp_tools": [],
            "pages": [],
            "page_schemas": [],
            "aesthetic_enabled": bool(self.settings.aesthetic_scoring_enabled),
            "aesthetic_suggestions": [],
            "build_status": "pending",
            "run_id": run_id,
            "run_status": "running",
            "data_model_migration": None,
            "verify_report": None,
            "verify_blocked": None,
            "current_node": None,
            "error": None,
        }

    def _emit_run_event(self, event_type: EventType, *, run_id: str, payload: Optional[dict[str, Any]] = None) -> None:
        self._emit(
            workflow_event(
                event_type,
                {
                    "run_id": run_id,
                    **(payload or {}),
                },
            )
        )

    def _create_run(
        self,
        *,
        user_message: str,
        generate_now: bool,
        style_reference: Optional[dict],
        target_pages: Optional[list[str]],
        run_service: RunService,
    ) -> SessionRun:
        run = run_service.create_run(
            session_id=self.session.id,
            message=user_message,
            generate_now=generate_now,
            style_reference=style_reference,
            target_pages=target_pages,
            trigger_source="chat",
        )
        if self.event_emitter is not None:
            self.event_emitter.run_id = run.id
        self._emit_run_event(
            EventType.RUN_CREATED,
            run_id=run.id,
            payload={"status": "queued", "checkpoint_thread": run.checkpoint_thread},
        )
        run_service.start_run(run.id)
        self._emit_run_event(
            EventType.RUN_STARTED,
            run_id=run.id,
            payload={"status": "running", "checkpoint_thread": run.checkpoint_thread},
        )
        return run

    def _resolve_resume_run(
        self,
        *,
        resume: dict[str, Any],
        run_service: RunService,
    ) -> SessionRun:
        resume_payload = dict(resume)
        run_id = resume_payload.get("run_id")
        if run_id is not None:
            run_id = str(run_id)
        run = run_service.resolve_resume_run(session_id=self.session.id, run_id=run_id)
        run_service.resume_run(run.id, resume_payload)
        if self.event_emitter is not None:
            self.event_emitter.run_id = run.id
        self._emit_run_event(
            EventType.RUN_RESUMED,
            run_id=run.id,
            payload={"status": "running", "checkpoint_thread": run.checkpoint_thread},
        )
        return run

    def _persist_run_state(self, state_store: StateStoreService, resolved_state: dict[str, Any]) -> None:
        run_id = resolved_state.get("run_id")
        if run_id is None:
            return
        run_status = resolved_state.get("run_status")
        if run_status is None:
            run_status = "running"
        graph_state = dict(resolved_state)
        graph_state["run_status"] = run_status
        state_store.update_metadata(
            self.session.id,
            {
                "graph_state": graph_state,
                "build_status": resolved_state.get("build_status"),
                "build_artifacts": resolved_state.get("build_artifacts"),
                "aesthetic_scores": resolved_state.get("aesthetic_scores"),
            },
        )

    def _check_cancelled(self, run_id: str, run_service: RunService) -> bool:
        if RunService.is_cancelled(run_id):
            return True
        try:
            self.db.expire_all()
            current = run_service.get_run(run_id)
            if current.status == "cancelled":
                RunService.mark_cancelled(run_id)
                return True
        except Exception:
            logger.debug("Failed to check run cancellation state", exc_info=True)
        return False

    async def stream_responses(
        self,
        *,
        user_message: str,
        output_dir: str,
        history: list[dict],
        trigger_interview: bool,
        generate_now: bool,
        style_reference: Optional[dict] = None,
        target_pages: Optional[list[str]] = None,
        resume: Optional[dict] = None,
    ) -> AsyncGenerator[OrchestratorResponse, None]:
        self._emit(
            AgentStartEvent(
                session_id=self.session.id,
                agent_id="langgraph",
                agent_type="LangGraph",
            )
        )

        if self._checkpointer is None:
            self._emit(
                ErrorEvent(
                    session_id=self.session.id,
                    message="LangGraph checkpointer disabled; resume is unavailable.",
                )
            )

        run_service = RunService(self.db)
        config = self._graph_config()
        run_record: SessionRun
        graph_input: Any

        try:
            if resume:
                run_record = self._resolve_resume_run(resume=resume, run_service=run_service)
                resume_payload = dict(resume)
                resume_payload["run_id"] = run_record.id
                graph_input = Command(resume=resume_payload)
            else:
                run_record = self._create_run(
                    user_message=user_message,
                    generate_now=generate_now,
                    style_reference=style_reference,
                    target_pages=target_pages,
                    run_service=run_service,
                )
                graph_input = self._build_initial_state(
                    user_message=user_message,
                    style_reference=style_reference,
                    run_id=run_record.id,
                )
            config = {
                "configurable": {
                    "thread_id": run_record.checkpoint_thread or f"{self.session.id}:{run_record.id}",
                }
            }
            self.db.commit()
        except RunStateConflictError as exc:
            self.db.rollback()
            message = str(exc)
            self._emit(ErrorEvent(session_id=self.session.id, message=message))
            self._emit(
                AgentEndEvent(
                    session_id=self.session.id,
                    agent_id="langgraph",
                    agent_type="LangGraph",
                    status="failed",
                    summary=message,
                )
            )
            yield OrchestratorResponse(
                session_id=self.session.id,
                phase="langgraph",
                message=message,
                is_complete=True,
                action="error",
            )
            return
        except Exception as exc:
            self.db.rollback()
            message = f"Failed to prepare run: {exc}"
            self._emit(ErrorEvent(session_id=self.session.id, message=message))
            self._emit(
                AgentEndEvent(
                    session_id=self.session.id,
                    agent_id="langgraph",
                    agent_type="LangGraph",
                    status="failed",
                    summary=message,
                )
            )
            yield OrchestratorResponse(
                session_id=self.session.id,
                phase="langgraph",
                message=message,
                is_complete=True,
                action="error",
            )
            return

        interrupted_payload: Any | None = None
        latest_state: dict | None = None
        try:
            async for update in self._graph.astream(
                graph_input,
                config=config,
                stream_mode=["updates"],
            ):
                normalized_update = self._normalize_stream_update(update)
                if isinstance(normalized_update, dict) and "__interrupt__" in normalized_update:
                    interrupted_payload = normalized_update.get("__interrupt__")
                    self._emit_interrupt(interrupted_payload)
                else:
                    latest_state = self._merge_updates(latest_state, normalized_update)
                if self._check_cancelled(run_record.id, run_service):
                    raise RunCancelledError(f"Run {run_record.id} cancelled")
        except RunCancelledError:
            resolved_state = await self._resolve_state(config, latest_state)
            resolved_state["run_id"] = run_record.id
            resolved_state["run_status"] = "cancelled"
            try:
                run_service.persist_run_state(run_record.id, "cancelled", finished_at=utcnow())
                if self.event_emitter is not None:
                    self.event_emitter.run_id = run_record.id
                self._emit_run_event(
                    EventType.RUN_CANCELLED,
                    run_id=run_record.id,
                    payload={"status": "cancelled"},
                )
                state_store = StateStoreService(self.db)
                self._persist_run_state(state_store, resolved_state)
                self.db.commit()
            except Exception:
                self.db.rollback()
                logger.exception("Failed to persist cancelled run state")
            yield OrchestratorResponse(
                session_id=self.session.id,
                phase="langgraph",
                message="Run cancelled.",
                is_complete=True,
                action="error",
                affected_pages=target_pages or [],
                product_doc_updated=False,
            )
            return
        except Exception as exc:
            run_service.persist_run_state(
                run_record.id,
                "failed",
                latest_error={"message": str(exc)},
                finished_at=utcnow(),
            )
            if self.event_emitter is not None:
                self.event_emitter.run_id = run_record.id
            self._emit_run_event(
                EventType.RUN_FAILED,
                run_id=run_record.id,
                payload={"status": "failed", "error": str(exc)},
            )
            self.db.commit()
            message = f"LangGraph execution failed: {exc}"
            self._emit(ErrorEvent(session_id=self.session.id, message=message))
            self._emit(
                AgentEndEvent(
                    session_id=self.session.id,
                    agent_id="langgraph",
                    agent_type="LangGraph",
                    status="failed",
                    summary=message,
                )
            )
            yield OrchestratorResponse(
                session_id=self.session.id,
                phase="langgraph",
                message=message,
                is_complete=True,
                action="error",
            )
            return

        resolved_state = await self._resolve_state(config, latest_state)
        resolved_state["run_id"] = run_record.id
        self._strip_runtime_fields(resolved_state)

        state_store = StateStoreService(self.db)
        try:
            self._persist_run_state(state_store, resolved_state)
        except Exception:
            logger.exception("Failed to persist LangGraph state")

        if interrupted_payload is not None:
            run_service.persist_run_state(run_record.id, "waiting_input")
            if self.event_emitter is not None:
                self.event_emitter.run_id = run_record.id
            self._emit_run_event(
                EventType.RUN_WAITING_INPUT,
                run_id=run_record.id,
                payload={"status": "waiting_input"},
            )
            resolved_state["run_status"] = "waiting_input"

            parsed_interrupt = self._parse_interrupt_payload(interrupted_payload)
            message = parsed_interrupt.get("message")
            if not message:
                message = "Waiting for feedback."

            try:
                self._persist_run_state(state_store, resolved_state)
                self.db.commit()
            except Exception:
                self.db.rollback()
                logger.exception("Failed to persist waiting_input run state")

            self._emit(
                AgentEndEvent(
                    session_id=self.session.id,
                    agent_id="langgraph",
                    agent_type="LangGraph",
                    status="success",
                    summary="LangGraph interrupted",
                )
            )
            self._emit(DoneEvent(session_id=self.session.id, summary="LangGraph waiting for feedback"))
            yield OrchestratorResponse(
                session_id=self.session.id,
                phase="langgraph",
                message=str(message),
                is_complete=True,
                action="refine_waiting",
                affected_pages=target_pages or [],
                product_doc_updated=False,
            )
            return

        run_service.persist_run_state(run_record.id, "completed")
        if self.event_emitter is not None:
            self.event_emitter.run_id = run_record.id
        completed_payload: dict[str, Any] = {"status": "completed"}
        migration_payload = resolved_state.get("data_model_migration")
        if isinstance(migration_payload, dict):
            completed_payload["data_model_migration"] = migration_payload
        self._emit_run_event(
            EventType.RUN_COMPLETED,
            run_id=run_record.id,
            payload=completed_payload,
        )
        resolved_state["run_status"] = "completed"
        try:
            self._persist_run_state(state_store, resolved_state)
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("Failed to persist completed run state")

        action = "direct_reply"
        if resolved_state.get("build_status") == "success" and resolved_state.get("page_schemas"):
            action = "pages_generated"

        self._emit(
            AgentEndEvent(
                session_id=self.session.id,
                agent_id="langgraph",
                agent_type="LangGraph",
                status="success",
                summary="LangGraph run completed",
            )
        )
        self._emit(DoneEvent(session_id=self.session.id, summary="LangGraph run completed"))

        yield OrchestratorResponse(
            session_id=self.session.id,
            phase="langgraph",
            message="LangGraph workflow completed.",
            is_complete=True,
            action=action,
            affected_pages=target_pages or [],
            product_doc_updated=False,
        )

    async def stream(
        self,
        *,
        user_message: str,
        output_dir: str,
        skip_interview: bool,
    ) -> AsyncGenerator[Any, None]:
        yield DoneEvent(session_id=self.session.id, summary="LangGraph idle")


__all__ = ["LangGraphOrchestrator"]
