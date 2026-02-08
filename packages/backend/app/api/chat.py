from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncGenerator, Generator, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session as DbSession

from ..agents.orchestrator import AgentOrchestrator, OrchestratorResponse
from ..config import get_settings
from ..db.models import Session as SessionModel
from ..db.utils import get_db
from ..db.database import get_database
from ..events.emitter import EventEmitter
from ..events.models import InterviewAnswerEvent, workflow_event
from ..schemas.chat import ChatRequest, ChatResponse
from ..services.message import MessageService
from ..services.page import PageService
from ..services.page_version import PageVersionService
from ..services.product_doc import ProductDocService
from ..events.types import EventType
from ..services.run import RunNotFoundError, RunService, RunStateConflictError
from ..services.session import SessionService
from ..services.token_tracker import TokenTrackerService
from ..services.image_storage import ImageStorageService
from ..services.event_store import EventStoreService
from ..utils.chat import parse_page_mentions
from ..utils.style import build_global_style_css
from .utils import build_page_preview_url, build_preview_url

router = APIRouter(prefix="/api/chat", tags=["chat"])

logger = logging.getLogger(__name__)

_INTERVIEW_PAYLOAD_RE = re.compile(r"<INTERVIEW_ANSWERS>(.*?)</INTERVIEW_ANSWERS>", re.DOTALL)

def _enqueue_stream_item(queue: "asyncio.Queue[object]", item: object) -> None:
    try:
        queue.put_nowait(item)
    except asyncio.QueueFull:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            return


def _log_stream_task_result(task: "asyncio.Task[object]") -> None:
    try:
        task.result()
    except Exception:
        logger.exception("Streaming task failed")


async def _run_orchestrator_stream(
    *,
    orchestrator: object,
    queue: "asyncio.Queue[object]",
    done_event: "asyncio.Event",
    user_message: str,
    output_dir: str,
    history: list[dict],
    trigger_interview: bool,
    generate_now: bool,
    style_reference: Optional[dict] = None,
    target_pages: Optional[list[str]] = None,
    resume: Optional[dict] = None,
    run_context: Optional["_ChatRunContext"] = None,
) -> None:
    final_message = ""
    final_response: Optional[OrchestratorResponse] = None
    stream_error: Optional[BaseException] = None
    try:
        async for response in orchestrator.stream_responses(
            user_message=user_message,
            output_dir=output_dir,
            history=history,
            trigger_interview=trigger_interview,
            generate_now=generate_now,
            style_reference=style_reference,
            target_pages=target_pages,
            resume=resume,
        ):
            final_response = response
            if response.message:
                final_message = response.message
            _enqueue_stream_item(queue, response)
    except Exception as exc:
        stream_error = exc
        _enqueue_stream_item(queue, exc)
    finally:
        try:
            if final_message:
                MessageService(orchestrator.db).add_message(
                    orchestrator.session.id, "assistant", final_message
                )
            _finalize_adapter_run(
                db=orchestrator.db,
                emitter=getattr(orchestrator, "event_emitter", None),
                run_context=run_context,
                final_response=final_response,
                error=stream_error,
            )
            orchestrator.db.commit()
        except Exception:
            orchestrator.db.rollback()
            logger.exception("Failed to persist streamed response")
        finally:
            done_event.set()
            try:
                orchestrator.db.close()
            except Exception:
                logger.exception("Failed to close streaming DB session")


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _create_orchestrator(
    db: DbSession,
    session: SessionModel,
    emitter: EventEmitter,
):
    settings = get_settings()
    if settings.use_langgraph:
        try:
            from ..graph.orchestrator import LangGraphOrchestrator

            return LangGraphOrchestrator(db, session, event_emitter=emitter)
        except Exception:
            logger.exception("LangGraph orchestrator unavailable; falling back to legacy")
    return AgentOrchestrator(db, session, event_emitter=emitter)


def _resolve_resume_payload(
    *,
    db: DbSession,
    session: SessionModel,
    resume_payload: Optional[dict],
) -> Optional[dict]:
    if not resume_payload:
        return None
    payload = dict(resume_payload)
    service = RunService(db)
    run_id = payload.get("run_id")
    try:
        run = service.resolve_resume_run(
            session_id=session.id,
            run_id=str(run_id) if run_id is not None else None,
        )
    except Exception:
        return payload
    payload["run_id"] = run.id
    return payload


def _active_run_id(*, db: DbSession, session_id: str, resume_payload: Optional[dict]) -> Optional[str]:
    if resume_payload and resume_payload.get("run_id"):
        return str(resume_payload.get("run_id"))
    service = RunService(db)
    waiting = service.get_latest_waiting_run(session_id)
    if waiting is not None:
        return waiting.id
    return None


@dataclass
class _ChatRunContext:
    run_id: Optional[str]
    resume_payload: Optional[dict]
    checkpoint_thread: Optional[str]
    adapter_active: bool
    transition: Optional[str] = None


def _log_chat_execution_mode(*, endpoint: str, settings) -> None:
    if settings.chat_use_run_adapter and not settings.use_langgraph:
        logger.info("[%s] chat run adapter path active", endpoint)
        return
    if settings.chat_use_run_adapter and settings.use_langgraph:
        logger.info(
            "[%s] chat_use_run_adapter enabled, but use_langgraph=true so run lifecycle stays orchestrator-managed",
            endpoint,
        )
        return
    logger.info("[%s] legacy chat path active", endpoint)


def _prepare_chat_run_context(
    *,
    db: DbSession,
    session: SessionModel,
    settings,
    message: str,
    generate_now: bool,
    style_reference: Optional[dict],
    target_pages: list[str],
    resume_payload: Optional[dict],
) -> _ChatRunContext:
    adapter_active = bool(settings.chat_use_run_adapter and not settings.use_langgraph)
    if not adapter_active:
        return _ChatRunContext(
            run_id=_active_run_id(db=db, session_id=session.id, resume_payload=resume_payload),
            resume_payload=resume_payload,
            checkpoint_thread=None,
            adapter_active=False,
            transition=None,
        )

    run_service = RunService(db)
    if resume_payload:
        resolved_payload = dict(resume_payload)
        requested_run_id = resolved_payload.get("run_id")
        try:
            run = run_service.resolve_resume_run(
                session_id=session.id,
                run_id=str(requested_run_id) if requested_run_id is not None else None,
            )
            resolved_payload["run_id"] = run.id
            run_service.resume_run(run.id, resolved_payload)
        except RunNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Run not found") from exc
        except RunStateConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        db.commit()
        return _ChatRunContext(
            run_id=run.id,
            resume_payload=resolved_payload,
            checkpoint_thread=run.checkpoint_thread,
            adapter_active=True,
            transition="resumed",
        )

    try:
        run = run_service.create_run(
            session_id=session.id,
            message=message,
            generate_now=bool(generate_now),
            style_reference=style_reference,
            target_pages=target_pages,
            trigger_source="chat",
        )
        run_service.start_run(run.id)
    except ValueError as exc:
        detail = str(exc)
        if detail == "Session not found":
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=422, detail=detail) from exc

    db.commit()
    return _ChatRunContext(
        run_id=run.id,
        resume_payload=resume_payload,
        checkpoint_thread=run.checkpoint_thread,
        adapter_active=True,
        transition="created",
    )


def _emit_adapter_transition_events(*, emitter: EventEmitter, run_context: _ChatRunContext) -> None:
    if not run_context.adapter_active or not run_context.run_id:
        return
    checkpoint_thread = run_context.checkpoint_thread
    if run_context.transition == "created":
        emitter.emit(
            workflow_event(
                EventType.RUN_CREATED,
                {
                    "status": "queued",
                    "checkpoint_thread": checkpoint_thread,
                },
            )
        )
        emitter.emit(
            workflow_event(
                EventType.RUN_STARTED,
                {
                    "status": "running",
                    "checkpoint_thread": checkpoint_thread,
                },
            )
        )
    elif run_context.transition == "resumed":
        emitter.emit(
            workflow_event(
                EventType.RUN_RESUMED,
                {
                    "status": "running",
                    "checkpoint_thread": checkpoint_thread,
                },
            )
        )


def _resolve_adapter_run_outcome(
    *,
    final_response: Optional[OrchestratorResponse],
    error: Optional[BaseException],
) -> tuple[str, dict, EventType, dict]:
    if error is not None:
        error_text = str(error) or "Chat orchestration failed"
        return (
            "failed",
            {"latest_error": {"message": error_text}},
            EventType.RUN_FAILED,
            {"status": "failed", "error": error_text},
        )

    if final_response is None:
        error_text = "No orchestrator response"
        return (
            "failed",
            {"latest_error": {"message": error_text}},
            EventType.RUN_FAILED,
            {"status": "failed", "error": error_text},
        )

    action = (final_response.action or "").strip().lower()
    if action == "error":
        error_text = final_response.message or "Run failed"
        return (
            "failed",
            {"latest_error": {"message": error_text}},
            EventType.RUN_FAILED,
            {"status": "failed", "error": error_text},
        )

    if action == "refine_waiting" or not bool(final_response.is_complete):
        waiting_reason = final_response.message or "Waiting for user input"
        return (
            "waiting_input",
            {"latest_error": {"waiting_reason": waiting_reason}},
            EventType.RUN_WAITING_INPUT,
            {"status": "waiting_input", "waiting_reason": waiting_reason},
        )

    return (
        "completed",
        {},
        EventType.RUN_COMPLETED,
        {"status": "completed"},
    )


def _finalize_adapter_run(
    *,
    db: DbSession,
    emitter: Optional[EventEmitter],
    run_context: Optional[_ChatRunContext],
    final_response: Optional[OrchestratorResponse],
    error: Optional[BaseException],
) -> None:
    if run_context is None or not run_context.adapter_active or not run_context.run_id:
        return

    run_service = RunService(db)
    status, update_kwargs, event_type, event_payload = _resolve_adapter_run_outcome(
        final_response=final_response,
        error=error,
    )

    try:
        run_service.persist_run_state(run_context.run_id, status, **update_kwargs)
    except RunNotFoundError:
        logger.warning("Run %s disappeared before finalization", run_context.run_id)
        return
    except RunStateConflictError:
        logger.info("Run %s already transitioned before adapter finalization", run_context.run_id)
        return

    if emitter is not None:
        emitter.emit(workflow_event(event_type, event_payload))


def _accepts_sse(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/event-stream" in accept


def _normalize_page_targets(
    targets: list[str],
    page_lookup: dict[str, str],
) -> list[str]:
    resolved: list[str] = []
    seen = set()
    for target in targets:
        if not target:
            continue
        cleaned = str(target).strip().lstrip("@")
        if not cleaned:
            continue
        slug = page_lookup.get(cleaned.lower())
        if not slug or slug in seen:
            continue
        resolved.append(slug)
        seen.add(slug)
    return resolved


def _merge_targets(primary: list[str], secondary: list[str]) -> list[str]:
    resolved = []
    seen = set()
    for entry in primary + secondary:
        if not entry or entry in seen:
            continue
        resolved.append(entry)
        seen.add(entry)
    return resolved


def _extract_interview_payload(message: str | None) -> Optional[dict]:
    if not message:
        return None
    match = _INTERVIEW_PAYLOAD_RE.search(message)
    if not match:
        return None
    payload_text = match.group(1).strip()
    if not payload_text:
        return None
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _token_total(db: DbSession, session_id: str) -> int:
    try:
        summary = TokenTrackerService(db).summarize_session(session_id)
    except Exception:
        return 0
    if not isinstance(summary, dict):
        return 0
    total = summary.get("total")
    if not isinstance(total, dict):
        return 0
    try:
        return int(total.get("total_tokens") or 0)
    except (TypeError, ValueError):
        return 0


def _build_preview_css(product_doc) -> Optional[str]:
    if product_doc is None:
        return None
    structured = getattr(product_doc, "structured", None)
    if not isinstance(structured, dict):
        structured = {}
    global_style = structured.get("global_style") or structured.get("globalStyle") or {}
    if not isinstance(global_style, dict):
        global_style = {}
    design_direction = structured.get("design_direction") or structured.get("designDirection") or {}
    if not isinstance(design_direction, dict):
        design_direction = {}
    try:
        return build_global_style_css(global_style, design_direction)
    except Exception:
        return None


def _resolve_preview(
    *,
    response: OrchestratorResponse,
    db: DbSession,
    session: SessionModel,
    request: Request,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    preview_url = response.preview_url
    preview_html = response.preview_html
    active_slug = response.active_page_slug

    page_service = PageService(db)
    pages = page_service.list_by_session(session.id)
    page_by_slug = {page.slug: page for page in pages}

    active_page = page_by_slug.get(active_slug) if active_slug else None
    if response.action == "pages_generated" and len(pages) > 1:
        index_page = page_by_slug.get("index")
        if index_page is not None:
            active_page = index_page
        elif active_page is None and pages:
            active_page = pages[0]

    if active_page is None and active_slug:
        active_page = page_by_slug.get(active_slug)

    if active_page is None and response.action in {"pages_generated", "page_refined"} and pages:
        if len(pages) == 1:
            active_page = pages[0]
        else:
            active_page = page_by_slug.get("index") or pages[0]

    if active_page is not None:
        active_slug = active_page.slug
        preview_url = build_page_preview_url(request, active_page.id)
        version_service = PageVersionService(db)
        product_doc = ProductDocService(db).get_by_session_id(session.id)
        global_style_css = _build_preview_css(product_doc)
        preview = version_service.build_preview(active_page.id, global_style_css=global_style_css)
        if preview is not None:
            _version, html = preview
            preview_html = html

    if preview_url is None:
        preview_url = build_preview_url(request, session.id)

    return preview_url, preview_html, active_slug


def _build_response_fields(
    *,
    response: OrchestratorResponse,
    db: DbSession,
    session: SessionModel,
    request: Request,
    start_tokens: int,
) -> dict:
    preview_url, preview_html, active_slug = _resolve_preview(
        response=response,
        db=db,
        session=session,
        request=request,
    )
    tokens_used = max(0, _token_total(db, session.id) - start_tokens)
    return {
        "preview_url": preview_url,
        "preview_html": preview_html,
        "active_page_slug": active_slug,
        "product_doc_updated": bool(response.product_doc_updated)
        if response.product_doc_updated is not None
        else False,
        "affected_pages": list(response.affected_pages) if response.affected_pages else [],
        "action": response.action or "direct_reply",
        "tokens_used": tokens_used,
    }


async def _stream_message_payload(
    *,
    message: str,
    final_payload: dict,
    chunk_size: int = 32,
) -> AsyncGenerator[str, None]:
    if not message:
        data = json.dumps(final_payload, ensure_ascii=False)
        yield f"data: {data}\n\n"
        return

    if len(message) <= chunk_size:
        payload = dict(final_payload)
        payload["message"] = message
        data = json.dumps(payload, ensure_ascii=False)
        yield f"data: {data}\n\n"
        return

    for start in range(0, len(message), chunk_size):
        chunk = message[start : start + chunk_size]
        data = json.dumps({"delta": chunk}, ensure_ascii=False)
        yield f"data: {data}\n\n"
        await asyncio.sleep(0)

    payload = dict(final_payload)
    payload["message"] = message
    data = json.dumps(payload, ensure_ascii=False)
    yield f"data: {data}\n\n"


@router.post("")
async def chat(
    payload: ChatRequest,
    request: Request,
    db: DbSession = Depends(_get_db_session),
):
    service = SessionService(db)
    session = db.get(SessionModel, payload.session_id) if payload.session_id else None
    if session is None:
        session = service.create_session(title=None)
        db.commit()
        db.refresh(session)

    settings = get_settings()
    _log_chat_execution_mode(endpoint="POST /api/chat", settings=settings)
    page_service = PageService(db)
    pages = page_service.list_by_session(session.id)
    page_lookup = {page.slug.lower(): page.slug for page in pages}
    explicit_targets = _normalize_page_targets(payload.target_pages, page_lookup)
    parsed_targets = parse_page_mentions(payload.message, page_lookup.values())
    target_pages = _merge_targets(explicit_targets, parsed_targets)
    scope_pages: list[str] = []
    if payload.style_reference and payload.style_reference.scope_pages:
        scope_pages = _normalize_page_targets(payload.style_reference.scope_pages, page_lookup)
    if not scope_pages:
        scope_pages = target_pages

    images = list(payload.images)
    if payload.style_reference and payload.style_reference.images:
        images.extend(payload.style_reference.images)
    images = [img for img in images if isinstance(img, str) and img.strip()]
    image_refs: list[dict] = []
    if images:
        storage_dir = Path(settings.output_dir) / "image-uploads"
        image_storage = ImageStorageService(str(storage_dir))
        for img in images[:3]:
            if ImageStorageService.is_url(img):
                image_refs.append({"id": None, "source": "url", "url": img})
                continue
            try:
                stored = await image_storage.save_image(img, session.id)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            image_refs.append(
                {
                    "id": stored.id,
                    "source": "upload",
                    "url": stored.url,
                    "content_type": stored.content_type,
                }
            )

    style_reference_mode = payload.style_reference_mode
    if payload.style_reference and payload.style_reference.mode:
        style_reference_mode = payload.style_reference.mode
    if style_reference_mode:
        session.style_reference_mode = style_reference_mode

    style_reference_tokens = None
    if payload.style_reference and payload.style_reference.tokens is not None:
        tokens_value = payload.style_reference.tokens
        if hasattr(tokens_value, "model_dump"):
            style_reference_tokens = tokens_value.model_dump()
        else:
            style_reference_tokens = tokens_value

    style_reference_context = None
    if image_refs or style_reference_tokens:
        style_reference_context = {
            "mode": style_reference_mode or "full_mimic",
            "scope": {
                "type": "specific_pages" if scope_pages else "model_decide",
                "pages": scope_pages,
            },
            "images": image_refs,
        }
        if style_reference_tokens:
            style_reference_context["tokens"] = style_reference_tokens

    message_service = MessageService(db)
    history_records = message_service.get_messages(session.id, limit=50)
    history = [{"role": msg.role, "content": msg.content} for msg in history_records]
    if payload.interview is None:
        trigger_interview = len(history_records) == 0
    else:
        trigger_interview = bool(payload.interview)
    message_service.add_message(session.id, "user", payload.message)
    db.commit()

    interview_payload = _extract_interview_payload(payload.message)
    start_tokens = _token_total(db, session.id)

    resolved_resume = _resolve_resume_payload(db=db, session=session, resume_payload=payload.resume)
    run_context = _prepare_chat_run_context(
        db=db,
        session=session,
        settings=settings,
        message=payload.message,
        generate_now=bool(payload.generate_now),
        style_reference=style_reference_context,
        target_pages=target_pages,
        resume_payload=resolved_resume,
    )
    resolved_resume = run_context.resume_payload

    if _accepts_sse(request):
        stream_db = get_database().session()
        stream_session = stream_db.get(SessionModel, session.id)
        if stream_session is None:
            stream_db.close()
            raise HTTPException(status_code=404, detail="Session not found")

        emitter = EventEmitter(
            session_id=stream_session.id,
            run_id=run_context.run_id,
            event_store=EventStoreService(stream_db),
        )
        _emit_adapter_transition_events(emitter=emitter, run_context=run_context)
        if interview_payload:
            emitter.emit(
                InterviewAnswerEvent(
                    session_id=session.id,
                    batch_id=interview_payload.get("batch_id")
                    or interview_payload.get("batchId"),
                    action=interview_payload.get("action"),
                    answers=interview_payload.get("answers"),
                )
            )
        orchestrator = _create_orchestrator(stream_db, stream_session, emitter)
        async def event_stream() -> AsyncGenerator[str, None]:
            index = 0
            responses_done = False
            response_queue: asyncio.Queue[object] = asyncio.Queue(maxsize=256)
            done_event = asyncio.Event()
            stream_task = asyncio.create_task(
                    _run_orchestrator_stream(
                        orchestrator=orchestrator,
                        queue=response_queue,
                        done_event=done_event,
                        user_message=payload.message,
                        output_dir=settings.output_dir,
                        history=history,
                        trigger_interview=trigger_interview,
                        generate_now=bool(payload.generate_now),
                        style_reference=style_reference_context,
                        target_pages=target_pages,
                        resume=resolved_resume,
                        run_context=run_context,
                    )
                )
            stream_task.add_done_callback(_log_stream_task_result)

            try:
                while True:
                    if await request.is_disconnected():
                        return

                    events, index = emitter.events_since(index)
                    for event in events:
                        if hasattr(event, "to_sse"):
                            yield event.to_sse()

                    should_drain_responses = (not responses_done) or (not response_queue.empty())
                    if should_drain_responses:
                        try:
                            item = await asyncio.wait_for(
                                response_queue.get(), timeout=0.05
                            )
                        except asyncio.TimeoutError:
                            item = None

                        if isinstance(item, BaseException):
                            raise item
                        elif item is not None:
                            response = item
                            response_fields = _build_response_fields(
                                response=response,
                                db=db,
                                session=session,
                                request=request,
                                start_tokens=start_tokens,
                            )
                            payload_data = response.to_payload()
                            message_text = payload_data.pop("message", "")
                            payload_data.update(response_fields)
                            async for chunk in _stream_message_payload(
                                message=message_text,
                                final_payload=payload_data,
                            ):
                                yield chunk
                    responses_done = done_event.is_set()

                    if responses_done and response_queue.empty() and not events:
                        break
            finally:
                pass
            events, index = emitter.events_since(index)
            for event in events:
                if hasattr(event, "to_sse"):
                    yield event.to_sse()

            try:
                db.commit()
            except Exception:
                logger.exception("Failed to commit session events")
            yield "data: [DONE]\n\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    emitter = EventEmitter(
        session_id=session.id,
        run_id=run_context.run_id,
        event_store=EventStoreService(db),
    )
    _emit_adapter_transition_events(emitter=emitter, run_context=run_context)
    if interview_payload:
        emitter.emit(
            InterviewAnswerEvent(
                session_id=session.id,
                batch_id=interview_payload.get("batch_id")
                or interview_payload.get("batchId"),
                action=interview_payload.get("action"),
                answers=interview_payload.get("answers"),
            )
        )
    orchestrator = _create_orchestrator(db, session, emitter)

    try:
        responses = [
            response
            async for response in orchestrator.stream_responses(
                user_message=payload.message,
                output_dir=settings.output_dir,
                history=history,
                trigger_interview=trigger_interview,
                generate_now=payload.generate_now,
                style_reference=style_reference_context,
                target_pages=target_pages,
                resume=resolved_resume,
            )
        ]
    except Exception as exc:
        _finalize_adapter_run(
            db=db,
            emitter=emitter,
            run_context=run_context,
            final_response=None,
            error=exc,
        )
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to persist run failure in chat adapter")
        raise

    final = responses[-1] if responses else None
    assistant_message = final.message if final else ""
    if assistant_message:
        message_service.add_message(session.id, "assistant", assistant_message)

    _finalize_adapter_run(
        db=db,
        emitter=emitter,
        run_context=run_context,
        final_response=final,
        error=None,
    )

    if assistant_message or run_context.adapter_active:
        db.commit()

    if final is not None:
        response_fields = _build_response_fields(
            response=final,
            db=db,
            session=session,
            request=request,
            start_tokens=start_tokens,
        )
    else:
        response_fields = {
            "preview_url": build_preview_url(request, session.id),
            "preview_html": None,
            "active_page_slug": None,
            "product_doc_updated": False,
            "affected_pages": [],
            "action": "direct_reply",
            "tokens_used": 0,
        }

    response_payload = ChatResponse(
        session_id=session.id,
        message=assistant_message,
        preview_url=response_fields["preview_url"],
        preview_html=response_fields["preview_html"],
        active_page_slug=response_fields["active_page_slug"],
        product_doc_updated=response_fields["product_doc_updated"],
        affected_pages=response_fields["affected_pages"],
        action=response_fields["action"],
        tokens_used=response_fields["tokens_used"],
    )
    return JSONResponse(response_payload.model_dump())


@router.post("/stream")
async def stream_post(
    payload: ChatRequest,
    request: Request,
    db: DbSession = Depends(_get_db_session),
):
    settings = get_settings()
    _log_chat_execution_mode(endpoint="POST /api/chat/stream", settings=settings)
    service = SessionService(db)
    session = db.get(SessionModel, payload.session_id) if payload.session_id else None
    if session is None:
        session = service.create_session(title=None)
        db.commit()
        db.refresh(session)

    page_service = PageService(db)
    pages = page_service.list_by_session(session.id)
    page_lookup = {page.slug.lower(): page.slug for page in pages}
    explicit_targets = _normalize_page_targets(payload.target_pages, page_lookup)
    parsed_targets = parse_page_mentions(payload.message, page_lookup.values())
    target_pages = _merge_targets(explicit_targets, parsed_targets)
    scope_pages: list[str] = []
    if payload.style_reference and payload.style_reference.scope_pages:
        scope_pages = _normalize_page_targets(payload.style_reference.scope_pages, page_lookup)
    if not scope_pages:
        scope_pages = target_pages

    images = list(payload.images)
    if payload.style_reference and payload.style_reference.images:
        images.extend(payload.style_reference.images)
    images = [img for img in images if isinstance(img, str) and img.strip()]
    image_refs: list[dict] = []
    if images:
        storage_dir = Path(settings.output_dir) / "image-uploads"
        image_storage = ImageStorageService(str(storage_dir))
        for img in images[:3]:
            if ImageStorageService.is_url(img):
                image_refs.append({"id": None, "source": "url", "url": img})
                continue
            try:
                stored = await image_storage.save_image(img, session.id)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            image_refs.append(
                {
                    "id": stored.id,
                    "source": "upload",
                    "url": stored.url,
                    "content_type": stored.content_type,
                }
            )

    style_reference_mode = payload.style_reference_mode
    if payload.style_reference and payload.style_reference.mode:
        style_reference_mode = payload.style_reference.mode
    if style_reference_mode:
        session.style_reference_mode = style_reference_mode

    style_reference_tokens = None
    if payload.style_reference and payload.style_reference.tokens is not None:
        tokens_value = payload.style_reference.tokens
        if hasattr(tokens_value, "model_dump"):
            style_reference_tokens = tokens_value.model_dump()
        else:
            style_reference_tokens = tokens_value

    style_reference_context = None
    if image_refs or style_reference_tokens:
        style_reference_context = {
            "mode": style_reference_mode or "full_mimic",
            "scope": {
                "type": "specific_pages" if scope_pages else "model_decide",
                "pages": scope_pages,
            },
            "images": image_refs,
        }
        if style_reference_tokens:
            style_reference_context["tokens"] = style_reference_tokens

    message_service = MessageService(db)
    history_records = message_service.get_messages(session.id, limit=50)
    history = [{"role": msg.role, "content": msg.content} for msg in history_records]
    if payload.interview is None:
        trigger_interview = len(history_records) == 0
    else:
        trigger_interview = bool(payload.interview)
    message_service.add_message(session.id, "user", payload.message)
    db.commit()

    resolved_resume = _resolve_resume_payload(db=db, session=session, resume_payload=payload.resume)
    run_context = _prepare_chat_run_context(
        db=db,
        session=session,
        settings=settings,
        message=payload.message,
        generate_now=bool(payload.generate_now),
        style_reference=style_reference_context,
        target_pages=target_pages,
        resume_payload=resolved_resume,
    )
    resolved_resume = run_context.resume_payload

    stream_db = get_database().session()
    stream_session = stream_db.get(SessionModel, session.id)
    if stream_session is None:
        stream_db.close()
        raise HTTPException(status_code=404, detail="Session not found")

    emitter = EventEmitter(
        session_id=stream_session.id,
        run_id=run_context.run_id,
        event_store=EventStoreService(stream_db),
    )
    _emit_adapter_transition_events(emitter=emitter, run_context=run_context)
    interview_payload = _extract_interview_payload(payload.message)
    if interview_payload:
        emitter.emit(
            InterviewAnswerEvent(
                session_id=session.id,
                batch_id=interview_payload.get("batch_id")
                or interview_payload.get("batchId"),
                action=interview_payload.get("action"),
                answers=interview_payload.get("answers"),
            )
        )
    orchestrator = _create_orchestrator(stream_db, stream_session, emitter)
    start_tokens = _token_total(db, session.id)

    async def event_stream() -> AsyncGenerator[str, None]:
        index = 0
        responses_done = False
        response_queue: asyncio.Queue[object] = asyncio.Queue(maxsize=256)
        done_event = asyncio.Event()
        stream_task = asyncio.create_task(
            _run_orchestrator_stream(
                orchestrator=orchestrator,
                queue=response_queue,
                done_event=done_event,
                user_message=payload.message,
                output_dir=settings.output_dir,
                history=history,
                trigger_interview=trigger_interview,
                generate_now=bool(payload.generate_now),
                style_reference=style_reference_context,
                target_pages=target_pages,
                resume=resolved_resume,
                run_context=run_context,
            )
        )
        stream_task.add_done_callback(_log_stream_task_result)

        try:
            while True:
                if await request.is_disconnected():
                    return

                events, index = emitter.events_since(index)
                for event in events:
                    if hasattr(event, "to_sse"):
                        yield event.to_sse()

                should_drain_responses = (not responses_done) or (not response_queue.empty())
                if should_drain_responses:
                    try:
                        item = await asyncio.wait_for(
                            response_queue.get(), timeout=0.05
                        )
                    except asyncio.TimeoutError:
                        item = None

                    if isinstance(item, BaseException):
                        raise item
                    elif item is not None:
                        response = item
                        response_fields = _build_response_fields(
                            response=response,
                            db=db,
                            session=session,
                            request=request,
                            start_tokens=start_tokens,
                        )
                        payload_data = response.to_payload()
                        message_text = payload_data.pop("message", "")
                        payload_data.update(response_fields)
                        async for chunk in _stream_message_payload(
                            message=message_text,
                            final_payload=payload_data,
                        ):
                            yield chunk
                responses_done = done_event.is_set()

                if responses_done and response_queue.empty() and not events:
                    break
        finally:
            pass
        events, index = emitter.events_since(index)
        for event in events:
            if hasattr(event, "to_sse"):
                yield event.to_sse()

        try:
            db.commit()
        except Exception:
            logger.exception("Failed to commit session events")
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/stream")
async def stream(
    request: Request,
    session_id: Optional[str] = None,
    message: Optional[str] = None,
    interview: Optional[bool] = None,
    generate_now: Optional[bool] = None,
    db: DbSession = Depends(_get_db_session),
):
    settings = get_settings()
    _log_chat_execution_mode(endpoint="GET /api/chat/stream", settings=settings)

    if message:
        service = SessionService(db)
        session = db.get(SessionModel, session_id) if session_id else None
        if session is None:
            session = service.create_session(title=None)
            db.commit()
            db.refresh(session)

        message_service = MessageService(db)
        history_records = message_service.get_messages(session.id, limit=50)
        history = [{"role": msg.role, "content": msg.content} for msg in history_records]
        if interview is None:
            trigger_interview = len(history_records) == 0
        else:
            trigger_interview = bool(interview)
        message_service.add_message(session.id, "user", message)
        db.commit()

        run_context = _prepare_chat_run_context(
            db=db,
            session=session,
            settings=settings,
            message=message,
            generate_now=bool(generate_now),
            style_reference=None,
            target_pages=[],
            resume_payload=None,
        )

        stream_db = get_database().session()
        stream_session = stream_db.get(SessionModel, session.id)
        if stream_session is None:
            stream_db.close()
            raise HTTPException(status_code=404, detail="Session not found")

        emitter = EventEmitter(
            session_id=stream_session.id,
            run_id=run_context.run_id,
            event_store=EventStoreService(stream_db),
        )
        _emit_adapter_transition_events(emitter=emitter, run_context=run_context)
        interview_payload = _extract_interview_payload(message)
        if interview_payload:
            emitter.emit(
                InterviewAnswerEvent(
                    session_id=session.id,
                    batch_id=interview_payload.get("batch_id")
                    or interview_payload.get("batchId"),
                    action=interview_payload.get("action"),
                    answers=interview_payload.get("answers"),
                )
            )
        orchestrator = _create_orchestrator(stream_db, stream_session, emitter)
        start_tokens = _token_total(db, session.id)

        async def event_stream() -> AsyncGenerator[str, None]:
            index = 0
            responses_done = False
            response_queue: asyncio.Queue[object] = asyncio.Queue(maxsize=256)
            done_event = asyncio.Event()
            stream_task = asyncio.create_task(
                _run_orchestrator_stream(
                    orchestrator=orchestrator,
                    queue=response_queue,
                    done_event=done_event,
                    user_message=message,
                    output_dir=settings.output_dir,
                    history=history,
                    trigger_interview=trigger_interview,
                    generate_now=bool(generate_now),
                    resume=run_context.resume_payload,
                    run_context=run_context,
                )
            )
            stream_task.add_done_callback(_log_stream_task_result)

            try:
                while True:
                    if await request.is_disconnected():
                        return

                    events, index = emitter.events_since(index)
                    for event in events:
                        if hasattr(event, "to_sse"):
                            yield event.to_sse()

                    should_drain_responses = (not responses_done) or (not response_queue.empty())
                    if should_drain_responses:
                        try:
                            item = await asyncio.wait_for(
                                response_queue.get(), timeout=0.05
                            )
                        except asyncio.TimeoutError:
                            item = None

                        if isinstance(item, BaseException):
                            raise item
                        elif item is not None:
                            response = item
                            response_fields = _build_response_fields(
                                response=response,
                                db=db,
                                session=session,
                                request=request,
                                start_tokens=start_tokens,
                            )
                            payload = response.to_payload()
                            message_text = payload.pop("message", "")
                            payload.update(response_fields)
                            async for chunk in _stream_message_payload(
                                message=message_text,
                                final_payload=payload,
                            ):
                                yield chunk
                    responses_done = done_event.is_set()

                    if responses_done and response_queue.empty() and not events:
                        break
            finally:
                pass
            events, index = emitter.events_since(index)
            for event in events:
                if hasattr(event, "to_sse"):
                    yield event.to_sse()

            try:
                db.commit()
            except Exception:
                logger.exception("Failed to commit session events")
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID required")

    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    orchestrator = _create_orchestrator(
        db,
        session,
        EventEmitter(session_id=session.id, event_store=EventStoreService(db)),
    )

    async def event_stream() -> AsyncGenerator[str, None]:
        async for event in orchestrator.stream(
            user_message="", output_dir=settings.output_dir, skip_interview=True
        ):
            if await request.is_disconnected():
                return
            if hasattr(event, "to_sse"):
                yield event.to_sse()
        try:
            db.commit()
        except Exception:
            logger.exception("Failed to commit session events")
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


__all__ = ["router"]
