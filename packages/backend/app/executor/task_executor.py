from __future__ import annotations

import json
from html.parser import HTMLParser
from datetime import datetime, timezone
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session as DbSession

from ..agents.component_builder import ComponentBuilderAgent
from ..agents.component_planner import ComponentPlannerAgent
from ..agents.generation import GenerationAgent
from ..agents.interview import InterviewAgent
from ..agents.refinement import RefinementAgent
from ..agents.validator import AestheticValidator
from ..config import Settings
from ..db.models import Page, Session as SessionModel, Task
from ..events.emitter import EventEmitter
from ..events.models import (
    AgentEndEvent,
    AgentProgressEvent,
    AgentStartEvent,
    AestheticScoreEvent,
    TaskProgressEvent,
)
from ..generators.mobile_html import validate_mobile_html
from ..services.export import ExportService
from ..services.page_version import PageVersionService
from ..services.product_doc import ProductDocService
from ..services.component_registry import ComponentRegistryService, slugify_component_id
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


def _normalize_component_plan(plan: Dict[str, Any], sitemap_pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    raw_components = plan.get("components") if isinstance(plan, dict) else []
    raw_page_map = plan.get("page_map") if isinstance(plan, dict) else None
    components: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    def add_component(item: Any) -> None:
        if isinstance(item, dict):
            name = item.get("name") or item.get("id") or item.get("title") or ""
            comp_id = slugify_component_id(item.get("id") or name)
            if not comp_id:
                return
            base = dict(item)
            base["id"] = comp_id
            if not base.get("name"):
                base["name"] = str(name or comp_id)
        else:
            name = str(item)
            comp_id = slugify_component_id(name)
            base = {"id": comp_id, "name": name}
        if comp_id in seen_ids:
            suffix = 2
            unique_id = f"{comp_id}-{suffix}"
            while unique_id in seen_ids:
                suffix += 1
                unique_id = f"{comp_id}-{suffix}"
            base["id"] = unique_id
            comp_id = unique_id
        seen_ids.add(comp_id)
        components.append(base)

    if isinstance(raw_components, list):
        for item in raw_components:
            add_component(item)

    page_map: Dict[str, List[str]] = {}
    name_map = {
        str(item.get("name") or item.get("id")).lower(): str(item.get("id"))
        for item in components
        if isinstance(item, dict)
    }
    id_map = {str(item.get("id")).lower(): str(item.get("id")) for item in components if isinstance(item, dict)}

    if isinstance(raw_page_map, dict):
        for page_slug, items in raw_page_map.items():
            if not isinstance(items, list):
                continue
            normalized_items: List[str] = []
            for raw in items:
                key = str(raw).lower()
                resolved = id_map.get(key) or name_map.get(key) or slugify_component_id(raw)
                if resolved:
                    normalized_items.append(resolved)
            if normalized_items:
                page_map[str(page_slug)] = normalized_items

    if not components:
        fallback_components, fallback_map = _fallback_components_from_pages(sitemap_pages)
        components = fallback_components
        page_map = fallback_map
    elif not page_map and sitemap_pages:
        for page in sitemap_pages:
            slug = str(page.get("slug") or "index")
            sections = page.get("sections") if isinstance(page.get("sections"), list) else []
            if sections:
                page_map[slug] = [slugify_component_id(section) for section in sections]

    if components and page_map:
        known_ids = {str(item.get("id")) for item in components if isinstance(item, dict) and item.get("id")}
        for ids in page_map.values():
            if not isinstance(ids, list):
                continue
            for comp_id in ids:
                if comp_id not in known_ids:
                    components.append({"id": comp_id, "name": comp_id})
                    known_ids.add(comp_id)

    return {"components": components, "page_map": page_map}


def _fallback_components_from_pages(
    sitemap_pages: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    components: Dict[str, Dict[str, Any]] = {}
    page_map: Dict[str, List[str]] = {}
    for page in sitemap_pages or []:
        slug = str(page.get("slug") or "index")
        sections = page.get("sections") if isinstance(page.get("sections"), list) else []
        ids: List[str] = []
        for section in sections:
            name = str(section)
            comp_id = slugify_component_id(name)
            if comp_id not in components:
                components[comp_id] = {
                    "id": comp_id,
                    "name": name,
                    "category": "section",
                    "sections": [name],
                }
            ids.append(comp_id)
        if ids:
            page_map[slug] = ids
    return list(components.values()), page_map


def _component_inventory(components: List[Dict[str, Any]]) -> List[str]:
    inventory: List[str] = []
    for item in components:
        name = item.get("name") or item.get("id")
        if name:
            inventory.append(str(name))
    return inventory


def _collect_dependency_context(context: ExecutionContext, task: Task) -> str:
    parts: List[str] = []
    for dep_result in context.dependency_results(task):
        if not isinstance(dep_result, dict):
            continue
        ctx = dep_result.get("context")
        if ctx:
            parts.append(f"Dependency context: {ctx}")
        message = dep_result.get("message")
        if message:
            parts.append(f"Dependency summary: {message}")
    return "\n".join(parts)


class _ComponentFragmentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.root_count = 0
        self.has_script = False
        self.has_text_outside = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "script":
            self.has_script = True
        if self.depth == 0:
            self.root_count += 1
        self.depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "script":
            self.has_script = True
        if self.depth == 0:
            self.root_count += 1

    def handle_endtag(self, tag: str) -> None:
        if self.depth > 0:
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        if self.depth == 0 and data.strip():
            self.has_text_outside = True


def _validate_component_html(html: Optional[str]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not html or not html.strip():
        return False, ["empty"]
    parser = _ComponentFragmentParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return False, ["parse_error"]
    if parser.has_script:
        reasons.append("contains_script")
    if parser.root_count != 1:
        reasons.append("invalid_root_count")
    if parser.has_text_outside:
        reasons.append("text_outside_root")
    return not reasons, reasons


def _component_registry_available(
    dependency_results: List[Dict[str, Any]],
    product_doc: Any,
) -> bool:
    for dep in dependency_results:
        if dep.get("component_registry_available") is False:
            return False
        if isinstance(dep.get("component_registry"), dict):
            return True
    structured = getattr(product_doc, "structured", None) if product_doc is not None else None
    if isinstance(structured, dict):
        registry_info = structured.get("component_registry")
        if hasattr(registry_info, "model_dump"):
            registry_info = registry_info.model_dump()
        if isinstance(registry_info, dict) and registry_info.get("path"):
            return True
    return False


def _component_sequence_for_page(
    dependency_results: List[Dict[str, Any]],
    page_slug: str,
) -> List[str]:
    for dep in dependency_results:
        plan = dep.get("component_registry_plan")
        if not isinstance(plan, dict):
            continue
        page_map = plan.get("page_map")
        if not isinstance(page_map, dict):
            continue
        sequence = page_map.get(page_slug) or page_map.get("index")
        if isinstance(sequence, list):
            return [str(item) for item in sequence if str(item).strip()]
    return []


def _component_ids_from_dependencies(dependency_results: List[Dict[str, Any]]) -> List[str]:
    for dep in dependency_results:
        components = dep.get("components")
        if isinstance(components, list):
            return [str(item) for item in components if str(item).strip()]
    return []


def _build_component_requirements(
    *,
    dependency_results: List[Dict[str, Any]],
    product_doc: Any,
    page_spec: Dict[str, Any] | None,
) -> str:
    if not _component_registry_available(dependency_results, product_doc):
        return ""
    slug = "index"
    if isinstance(page_spec, dict):
        slug = str(page_spec.get("slug") or "index")
    component_ids = _component_ids_from_dependencies(dependency_results)
    sequence = _component_sequence_for_page(dependency_results, slug)
    parts = ["Component registry available."]
    if component_ids:
        parts.append(f"Allowed component ids: {', '.join(component_ids)}.")
    if sequence:
        parts.append(f"Component sequence for page '{slug}': {', '.join(sequence)}.")
    parts.append("Use <component id=\"...\" data='{\"slot\":\"value\"}'></component> placeholders for these components.")
    return "\n".join(parts)


def _resolve_component_plan(
    payload: Dict[str, Any],
    dependency_results: List[Dict[str, Any]],
    product_doc: Any,
) -> Dict[str, Any]:
    plan = None
    for dep in dependency_results:
        if isinstance(dep, dict) and isinstance(dep.get("component_registry_plan"), dict):
            plan = dep.get("component_registry_plan")
            break
    if plan is None and isinstance(payload, dict):
        plan = payload.get("component_registry_plan")
    if plan is None and product_doc is not None:
        structured = getattr(product_doc, "structured", None)
        if isinstance(structured, dict):
            plan = structured.get("component_registry_plan")
    if not isinstance(plan, dict):
        plan = {}
    pages = payload.get("sitemap_pages") if isinstance(payload.get("sitemap_pages"), list) else []
    return _normalize_component_plan(plan, pages)


def _write_component_registry(
    *,
    context: ExecutionContext,
    plan: Dict[str, Any],
    components: List[Dict[str, Any]],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    service = ComponentRegistryService(context.output_dir, context.session_id)
    built_map = {
        slugify_component_id(item.get("id")): item
        for item in components
        if isinstance(item, dict) and item.get("id")
    }
    page_map = plan.get("page_map") if isinstance(plan.get("page_map"), dict) else {}
    registry_components: List[Dict[str, Any]] = []

    usage_map: Dict[str, List[str]] = {}
    for page_slug, ids in page_map.items():
        if not isinstance(ids, list):
            continue
        for comp_id in ids:
            usage_map.setdefault(str(comp_id), []).append(str(page_slug))

    for spec in plan.get("components", []):
        if not isinstance(spec, dict):
            continue
        comp_id = spec.get("id") or spec.get("name")
        if not comp_id:
            continue
        comp_id = slugify_component_id(comp_id)
        built = built_map.get(comp_id, {})
        name = spec.get("name") or built.get("name") or comp_id
        file_name = f"{comp_id}.html"
        file_path = f"components/{file_name}"
        html = built.get("html") if isinstance(built, dict) else None
        if html:
            valid, reasons = _validate_component_html(html)
            if not valid:
                logger.warning(
                    "Invalid component HTML for %s; reasons=%s",
                    comp_id,
                    ", ".join(reasons) if reasons else "unknown",
                )
                html = None
        if not html:
            html = f'<section data-component="{comp_id}"></section>'
        service.write_component(file_name, html)
        registry_components.append(
            {
                "id": comp_id,
                "name": name,
                "category": spec.get("category"),
                "sections": spec.get("sections"),
                "slots": built.get("slots") if isinstance(built, dict) else None,
                "props": built.get("props") if isinstance(built, dict) else None,
                "usage": {"pages": usage_map.get(comp_id, [])},
                "file": file_path,
            }
        )

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    registry = {
        "version": 1,
        "session_id": context.session_id,
        "generated_at": generated_at,
        "components": registry_components,
        "page_map": page_map,
    }
    registry["hash"] = service.compute_hash(registry)
    service.write_registry(registry)
    registry_info = {
        "path": "components/components.json",
        "version": registry["version"],
        "hash": registry["hash"],
        "generated_at": generated_at,
    }
    return registry, registry_info


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


class ComponentPlanTaskExecutor(BaseTaskExecutor):
    agent_type_label = "ComponentPlan"

    async def execute(self, task: Task, emitter: EventEmitter, context: ExecutionContext) -> Dict[str, Any]:
        agent_id = self._agent_id(task)
        self._emit_agent_start(emitter, task, agent_id)
        payload = _safe_json_loads(task.description) or {}
        pages = payload.get("sitemap_pages") or payload.get("pages") or []
        if not isinstance(pages, list):
            pages = []
        design_direction = payload.get("design_direction") if isinstance(payload, dict) else {}
        if not isinstance(design_direction, dict):
            design_direction = {}

        agent = ComponentPlannerAgent(
            context.db,
            context.session_id,
            context.settings,
            event_emitter=emitter,
            agent_id=agent_id,
            task_id=task.id,
            emit_lifecycle_events=False,
        )
        product_doc = ProductDocService(context.db).get_by_session_id(context.session_id)
        try:
            result = await agent.plan(
                product_doc=product_doc,
                sitemap_pages=pages,
                design_direction=design_direction,
            )
            plan_source = result.plan
        except Exception:
            logger.exception("Component planning failed; using fallback plan")
            plan_source = {}
        plan = _normalize_component_plan(plan_source, pages)
        inventory = _component_inventory(plan.get("components", []))
        if product_doc is not None:
            ProductDocService(context.db, event_emitter=emitter).update(
                product_doc.id,
                structured={
                    "component_registry_plan": plan,
                    "component_inventory": inventory,
                },
                change_summary="Component plan generated",
            )

        summary = "Component plan ready"
        component_ids = [item.get("id") for item in plan.get("components", []) if isinstance(item, dict)]
        context_text = f"Component plan ids: {', '.join(component_ids)}"
        self._emit_agent_end(emitter, task, agent_id, status="success", summary=summary)
        return {
            "component_registry_plan": plan,
            "component_inventory": inventory,
            "context": context_text,
            "message": summary,
        }


class ComponentBuildTaskExecutor(BaseTaskExecutor):
    agent_type_label = "ComponentBuild"

    async def execute(self, task: Task, emitter: EventEmitter, context: ExecutionContext) -> Dict[str, Any]:
        agent_id = self._agent_id(task)
        self._emit_agent_start(emitter, task, agent_id)
        payload = _safe_json_loads(task.description) or {}
        design_direction = payload.get("design_direction") if isinstance(payload, dict) else {}
        if not isinstance(design_direction, dict):
            design_direction = {}

        product_doc = ProductDocService(context.db).get_by_session_id(context.session_id)
        plan = _resolve_component_plan(payload, context.dependency_results(task), product_doc)
        agent = ComponentBuilderAgent(
            context.db,
            context.session_id,
            context.settings,
            event_emitter=emitter,
            agent_id=agent_id,
            task_id=task.id,
            emit_lifecycle_events=False,
        )
        try:
            result = await agent.build(
                component_plan=plan,
                design_direction=design_direction,
                product_doc=product_doc,
            )
            built_components = result.components
        except Exception:
            logger.exception("Component build failed; using fallback components")
            built_components = []
        if not built_components:
            summary = "Component build failed; falling back to direct page generation"
            self._emit_agent_end(emitter, task, agent_id, status="success", summary=summary)
            return {
                "component_registry": None,
                "components": [],
                "context": "",
                "message": summary,
                "component_registry_available": False,
            }

        registry, registry_info = _write_component_registry(
            context=context,
            plan=plan,
            components=built_components,
        )
        if product_doc is not None:
            ProductDocService(context.db, event_emitter=emitter).update(
                product_doc.id,
                structured={"component_registry": registry_info},
                change_summary="Component registry generated",
            )

        summary = "Component registry ready"
        component_ids = [item.get("id") for item in registry.get("components", []) if isinstance(item, dict)]
        context_text = f"Component registry ids: {', '.join(component_ids)}."
        self._emit_agent_end(emitter, task, agent_id, status="success", summary=summary)
        return {
            "component_registry": registry_info,
            "components": component_ids,
            "context": context_text,
            "message": summary,
            "component_registry_available": True,
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
            dependency_results = context.dependency_results(task)
            dependency_context = _collect_dependency_context(context, task)
            if dependency_context:
                requirements = "\n\n".join([part for part in [requirements, dependency_context] if part])
            page_spec = payload.get("page_spec")
            nav = payload.get("nav") or []
            global_style = payload.get("global_style") or {}
            all_pages = payload.get("all_pages") or []
            guardrails = payload.get("guardrails") if isinstance(payload, dict) else None
            page_id = payload.get("page_id")
            current_html = None
            if page_id:
                page_version_service = PageVersionService(context.db)
                current = page_version_service.get_current(page_id)
                if current is None:
                    versions = page_version_service.list_by_page(page_id)
                    current = versions[0] if versions else None
                if current is not None:
                    current_html = current.html
            product_doc = ProductDocService(context.db).get_by_session_id(context.session_id)
            component_notes = _build_component_requirements(
                dependency_results=dependency_results,
                product_doc=product_doc,
                page_spec=page_spec if isinstance(page_spec, dict) else None,
            )
            if component_notes:
                requirements = "\n\n".join([part for part in [requirements, component_notes] if part])

            result = await agent.generate(
                requirements=requirements,
                output_dir=context.output_dir,
                history=context.history,
                current_html=current_html,
                page_id=page_id,
                page_spec=page_spec,
                global_style=global_style,
                nav=nav,
                product_doc=product_doc,
                all_pages=all_pages,
                guardrails=guardrails,
            )
        else:
            requirements = context.build_requirements(task)
            product_doc = ProductDocService(context.db).get_by_session_id(context.session_id)
            result = await agent.generate(
                requirements=requirements,
                output_dir=context.output_dir,
                history=context.history,
                product_doc=product_doc,
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
        guardrails = payload.get("guardrails") if isinstance(payload, dict) else None
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
        result = validate_mobile_html(html, guardrails=guardrails)
        errors = result.get("errors", []) if isinstance(result, dict) else []
        warnings = result.get("warnings", []) if isinstance(result, dict) else []

        aesthetic_score = None
        aesthetic_attempts_payload = None
        refined = False
        session = context.db.get(SessionModel, context.session_id)
        product_type = session.product_type if session else None
        if not product_type:
            product_doc = ProductDocService(context.db).get_by_session_id(context.session_id)
            structured = getattr(product_doc, "structured", None)
            if isinstance(structured, dict):
                product_type = structured.get("product_type") or structured.get("productType")

        if page_id and product_type:
            validator = AestheticValidator(context.db, context.session_id, context.settings, event_emitter=emitter)
            try:
                final_html, final_score, attempts = await validator.validate_and_refine(
                    html,
                    product_type=product_type,
                )
                if final_score is not None:
                    aesthetic_score = final_score
                    aesthetic_attempts_payload = [
                        {
                            "version": attempt.version,
                            "total": attempt.score.total,
                            "issues": attempt.score.issues,
                            "passes_threshold": attempt.score.passes_threshold,
                            "timestamp": attempt.timestamp.isoformat().replace("+00:00", "Z"),
                        }
                        for attempt in attempts
                    ]
                    page = context.db.get(Page, page_id)
                    emitter.emit(
                        AestheticScoreEvent(
                            page_id=page_id,
                            slug=page.slug if page else None,
                            score=final_score.model_dump(mode="json"),
                            attempts=aesthetic_attempts_payload,
                        )
                    )
                if final_html and final_html != html:
                    PageVersionService(context.db, event_emitter=emitter).create(
                        page_id,
                        final_html,
                        description="Aesthetic refinement",
                    )
                    refined = True
                    html = final_html
            except Exception:
                logger.exception("Aesthetic validation failed; continuing with original HTML")

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
            "aesthetic_score": aesthetic_score.model_dump(mode="json") if aesthetic_score else None,
            "aesthetic_refined": refined,
            "aesthetic_attempts": aesthetic_attempts_payload,
        }


class TaskExecutorFactory:
    _executors = {
        "interview": InterviewTaskExecutor,
        "component_plan": ComponentPlanTaskExecutor,
        "component_build": ComponentBuildTaskExecutor,
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
    "ComponentPlanTaskExecutor",
    "ComponentBuildTaskExecutor",
    "GenerationTaskExecutor",
    "RefinementTaskExecutor",
    "ExportTaskExecutor",
    "ValidatorTaskExecutor",
    "TaskExecutorFactory",
]
