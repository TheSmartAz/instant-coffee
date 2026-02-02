from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session as DbSession

from ..agents.generation import GenerationAgent
from ..agents.interview import InterviewAgent
from ..agents.refinement import RefinementAgent
from ..config import Settings
from ..db.models import Task
from ..events.emitter import EventEmitter
from ..events.models import (
    AgentEndEvent,
    AgentProgressEvent,
    AgentStartEvent,
    TaskProgressEvent,
)
from ..generators.mobile_html import validate_mobile_html
from ..services.export import ExportService
from ..services.page_version import PageVersionService
from ..services.product_doc import ProductDocService
from ..services.task import TaskService
from ..services.version import VersionService

logger = logging.getLogger(__name__)


def _safe_json_loads(value: Optional[str]) -> Optional[Dict[str, Any]]:
    if not value:
        return None
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
        return {"value": parsed}
    except json.JSONDecodeError:
        return None


def _parse_depends_on(value: Optional[str]) -> List[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        return [value]
    return [value]


@dataclass
class ExecutionContext:
    db: DbSession
    session_id: str
    settings: Settings
    output_dir: str
    history: Sequence[Dict[str, str]]
    user_message: str
    plan_goal: str
    task_service: TaskService
    task_lookup: Dict[str, Task]

    def dependency_results(self, task: Task) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for dep_id in _parse_depends_on(task.depends_on):
            dep_task = self.task_lookup.get(dep_id)
            if dep_task is None:
                continue
            parsed = _safe_json_loads(dep_task.result)
            if parsed:
                results.append(parsed)
        return results

    def build_requirements(self, task: Task) -> str:
        parts: List[str] = []
        base = task.description or self.plan_goal or self.user_message
        if base:
            parts.append(str(base))

        for dep_result in self.dependency_results(task):
            context = dep_result.get("context")
            if context:
                parts.append(f"Dependency context: {context}")
            message = dep_result.get("message")
            if message:
                parts.append(f"Dependency summary: {message}")

        if self.history:
            history_lines = []
            for item in self.history[-10:]:
                role = item.get("role", "user")
                content = item.get("content", "")
                if content:
                    history_lines.append(f"{role}: {content}")
            if history_lines:
                parts.append("Conversation history:\n" + "\n".join(history_lines))

        return "\n\n".join([part for part in parts if part])


class BaseTaskExecutor(ABC):
    agent_type_label: str

    @abstractmethod
    async def execute(self, task: Task, emitter: EventEmitter, context: ExecutionContext) -> Dict[str, Any]:
        raise NotImplementedError

    def _agent_id(self, task: Task) -> str:
        return f"{self.agent_type_label.lower()}_{task.id}"

    def _emit_agent_start(self, emitter: EventEmitter, task: Task, agent_id: str) -> None:
        emitter.emit(
            AgentStartEvent(
                task_id=task.id,
                agent_id=agent_id,
                agent_type=self.agent_type_label,
            )
        )

    def _emit_agent_progress(
        self,
        emitter: EventEmitter,
        task: Task,
        agent_id: str,
        message: str,
        progress: Optional[int] = None,
    ) -> None:
        emitter.emit(
            AgentProgressEvent(
                task_id=task.id,
                agent_id=agent_id,
                message=message,
                progress=progress,
            )
        )

    def _emit_task_progress(
        self,
        emitter: EventEmitter,
        context: ExecutionContext,
        task: Task,
        progress: int,
        message: Optional[str] = None,
    ) -> None:
        emitter.emit(TaskProgressEvent(task_id=task.id, progress=progress, message=message))
        try:
            context.task_service.update_task(task.id, progress=progress)
        except Exception:
            logger.exception("Failed to update task progress")

    def _emit_agent_end(
        self, emitter: EventEmitter, task: Task, agent_id: str, status: str, summary: str
    ) -> None:
        emitter.emit(
            AgentEndEvent(
                task_id=task.id,
                agent_id=agent_id,
                status=status,
                summary=summary,
            )
        )


class InterviewTaskExecutor(BaseTaskExecutor):
    agent_type_label = "Interview"

    async def execute(self, task: Task, emitter: EventEmitter, context: ExecutionContext) -> Dict[str, Any]:
        agent_id = self._agent_id(task)
        self._emit_agent_start(emitter, task, agent_id)
        agent = InterviewAgent(
            context.db,
            context.session_id,
            context.settings,
            event_emitter=emitter,
            agent_id=agent_id,
            task_id=task.id,
            emit_lifecycle_events=False,
        )
        user_input = task.description or context.user_message or context.plan_goal
        result = await agent.process(user_input or "", context.history)
        self._emit_agent_progress(
            emitter,
            task,
            agent_id,
            message=result.message,
        )
        self._emit_agent_end(
            emitter,
            task,
            agent_id,
            status="success",
            summary=result.message,
        )
        return {
            "message": result.message,
            "is_complete": result.is_complete,
            "confidence": result.confidence,
            "context": result.context,
            "rounds_used": result.rounds_used,
        }


class GenerationTaskExecutor(BaseTaskExecutor):
    agent_type_label = "Generation"

    async def execute(self, task: Task, emitter: EventEmitter, context: ExecutionContext) -> Dict[str, Any]:
        agent_id = self._agent_id(task)
        self._emit_agent_start(emitter, task, agent_id)
        agent = GenerationAgent(
            context.db,
            context.session_id,
            context.settings,
            event_emitter=emitter,
            agent_id=agent_id,
            task_id=task.id,
            emit_lifecycle_events=False,
        )

        steps = agent.progress_steps()
        for step in steps[:-1]:
            self._emit_agent_progress(
                emitter,
                task,
                agent_id,
                message=step.message,
                progress=step.progress,
            )
            self._emit_task_progress(
                emitter,
                context,
                task,
                progress=step.progress,
                message=step.message,
            )

        payload = _safe_json_loads(task.description)
        if payload and isinstance(payload, dict) and payload.get("page_spec"):
            requirements = payload.get("requirements") or context.user_message or context.plan_goal
            page_spec = payload.get("page_spec")
            nav = payload.get("nav") or []
            global_style = payload.get("global_style") or {}
            all_pages = payload.get("all_pages") or []
            page_id = payload.get("page_id")
            product_doc = ProductDocService(context.db).get_by_session_id(context.session_id)

            result = await agent.generate(
                requirements=requirements,
                output_dir=context.output_dir,
                history=context.history,
                page_id=page_id,
                page_spec=page_spec,
                global_style=global_style,
                nav=nav,
                product_doc=product_doc,
                all_pages=all_pages,
            )
        else:
            requirements = context.build_requirements(task)
            result = await agent.generate(
                requirements=requirements,
                output_dir=context.output_dir,
                history=context.history,
            )

            VersionService(context.db).create_version(
                context.session_id,
                result.html,
                description=task.title or "Generate page",
            )

        self._emit_agent_end(
            emitter,
            task,
            agent_id,
            status="success",
            summary="Page generation complete",
        )
        return {
            "output_file": result.filepath,
            "preview_url": result.preview_url,
            "page_id": getattr(result, "page_id", None),
            "fallback_used": getattr(result, "fallback_used", False),
            "fallback_excerpt": getattr(result, "fallback_excerpt", None),
        }


class RefinementTaskExecutor(BaseTaskExecutor):
    agent_type_label = "Refinement"

    async def execute(self, task: Task, emitter: EventEmitter, context: ExecutionContext) -> Dict[str, Any]:
        agent_id = self._agent_id(task)
        self._emit_agent_start(emitter, task, agent_id)
        version_service = VersionService(context.db)
        versions = version_service.get_versions(context.session_id, limit=1)
        if not versions:
            raise ValueError("No version available for refinement")
        current_html = versions[0].html
        agent = RefinementAgent(
            context.db,
            context.session_id,
            context.settings,
            event_emitter=emitter,
            agent_id=agent_id,
            task_id=task.id,
            emit_lifecycle_events=False,
        )
        user_input = task.description or context.user_message
        result = await agent.refine(
            user_input=user_input or "",
            current_html=current_html,
            output_dir=context.output_dir,
        )

        version_service.create_version(
            context.session_id,
            result.html,
            description=task.title or "Refinement",
        )

        self._emit_agent_end(
            emitter,
            task,
            agent_id,
            status="success",
            summary="Page refinement complete",
        )
        return {
            "output_file": result.filepath,
            "preview_url": result.preview_url,
        }


class ExportTaskExecutor(BaseTaskExecutor):
    agent_type_label = "Export"

    async def execute(self, task: Task, emitter: EventEmitter, context: ExecutionContext) -> Dict[str, Any]:
        agent_id = self._agent_id(task)
        self._emit_agent_start(emitter, task, agent_id)
        payload = _safe_json_loads(task.description)
        page_order = None
        global_style = None
        include_product_doc = True
        if isinstance(payload, dict):
            page_order = payload.get("pages")
            global_style = payload.get("global_style")
            include_product_doc = payload.get("include_product_doc", True)

        service = ExportService(context.db)
        result = await service.export_session(
            session_id=context.session_id,
            output_dir=context.output_dir,
            page_order=page_order,
            global_style=global_style,
            include_product_doc=include_product_doc,
        )
        output_files = []
        for page in result.manifest.get("pages", []):
            if page.get("status") == "success" and page.get("path"):
                output_files.append(str(result.export_dir / page["path"]))
        for asset in result.manifest.get("assets", []):
            asset_path = asset.get("path")
            if asset_path:
                output_files.append(str(result.export_dir / asset_path))
        if result.manifest.get("product_doc", {}).get("included"):
            output_files.append(str(result.export_dir / "product-doc.md"))
        manifest_path = result.export_dir / "export_manifest.json"
        self._emit_agent_end(
            emitter,
            task,
            agent_id,
            status="success",
            summary="Export complete",
        )
        return {
            "output_files": output_files,
            "session_dir": str(result.export_dir),
            "manifest_file": str(manifest_path),
            "success": result.success,
            "errors": result.errors,
        }


class ValidatorTaskExecutor(BaseTaskExecutor):
    agent_type_label = "Validator"

    async def execute(self, task: Task, emitter: EventEmitter, context: ExecutionContext) -> Dict[str, Any]:
        agent_id = self._agent_id(task)
        self._emit_agent_start(emitter, task, agent_id)
        payload = _safe_json_loads(task.description)
        page_id = payload.get("page_id") if isinstance(payload, dict) else None
        if page_id:
            page_version_service = PageVersionService(context.db)
            current = page_version_service.get_current(page_id)
            if current is None:
                versions = page_version_service.list_by_page(page_id)
                current = versions[0] if versions else None
            if current is None:
                raise ValueError("No page version available for validation")
            html = current.html
        else:
            version_service = VersionService(context.db)
            versions = version_service.get_versions(context.session_id, limit=1)
            if not versions:
                raise ValueError("No version available for validation")
            html = versions[0].html
        result = validate_mobile_html(html)
        errors = result.get("errors", []) if isinstance(result, dict) else []
        warnings = result.get("warnings", []) if isinstance(result, dict) else []
        summary = "Validation passed" if not errors else "Validation completed with issues"
        self._emit_agent_end(
            emitter,
            task,
            agent_id,
            status="success",
            summary=summary,
        )
        return {
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "page_id": page_id,
        }


class TaskExecutorFactory:
    _executors = {
        "interview": InterviewTaskExecutor,
        "generation": GenerationTaskExecutor,
        "refinement": RefinementTaskExecutor,
        "export": ExportTaskExecutor,
        "validator": ValidatorTaskExecutor,
    }

    @classmethod
    def create(cls, agent_type: Optional[str]) -> BaseTaskExecutor:
        resolved = (agent_type or "generation").strip().lower()
        executor_class = cls._executors.get(resolved)
        if not executor_class:
            raise ValueError(f"Unknown agent type: {agent_type}")
        return executor_class()


__all__ = [
    "ExecutionContext",
    "BaseTaskExecutor",
    "InterviewTaskExecutor",
    "GenerationTaskExecutor",
    "RefinementTaskExecutor",
    "ExportTaskExecutor",
    "ValidatorTaskExecutor",
    "TaskExecutorFactory",
]
