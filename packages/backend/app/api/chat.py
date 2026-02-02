from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import AsyncGenerator, Generator, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session as DbSession

from ..agents.orchestrator import AgentOrchestrator, OrchestratorResponse
from ..config import get_settings
from ..db.models import Session as SessionModel
from ..db.utils import get_db
from ..events.emitter import EventEmitter
from ..events.models import InterviewAnswerEvent
from ..schemas.chat import ChatRequest, ChatResponse
from ..services.message import MessageService
from ..services.page import PageService
from ..services.page_version import PageVersionService
from ..services.product_doc import ProductDocService
from ..services.session import SessionService
from ..services.task import TaskService
from ..services.token_tracker import TokenTrackerService
from ..services.event_store import EventStoreService
from ..utils.style import build_global_style_css
from ..executor.manager import ExecutorManager
from .utils import build_page_preview_url, build_preview_url

router = APIRouter(prefix="/api/chat", tags=["chat"])

logger = logging.getLogger(__name__)

_INTERVIEW_PAYLOAD_RE = re.compile(r"<INTERVIEW_ANSWERS>(.*?)</INTERVIEW_ANSWERS>", re.DOTALL)


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _accepts_sse(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/event-stream" in accept


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


def _abort_session_execution(db: DbSession, session_id: str) -> None:
    service = TaskService(db)
    plan_ids, _completed, _aborted = service.abort_session_with_details(session_id)
    if plan_ids:
        manager = ExecutorManager.get_instance()
        for plan_id in plan_ids:
            manager.abort(plan_id)
        db.commit()


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

    message_service = MessageService(db)
    history_records = message_service.get_messages(session.id, limit=50)
    history = [{"role": msg.role, "content": msg.content} for msg in history_records]
    if payload.interview is None:
        trigger_interview = len(history_records) == 0
    else:
        trigger_interview = bool(payload.interview)
    message_service.add_message(session.id, "user", payload.message)
    db.commit()

    emitter = EventEmitter(session_id=session.id, event_store=EventStoreService(db))
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
    orchestrator = AgentOrchestrator(db, session, event_emitter=emitter)
    settings = get_settings()
    start_tokens = _token_total(db, session.id)

    if _accepts_sse(request):
        async def event_stream() -> AsyncGenerator[str, None]:
            index = 0

            def drain() -> list:
                nonlocal index
                events, index = emitter.events_since(index)
                return events

            async for response in orchestrator.stream_responses(
                user_message=payload.message,
                output_dir=settings.output_dir,
                history=history,
                trigger_interview=trigger_interview,
                generate_now=payload.generate_now,
            ):
                if await request.is_disconnected():
                    _abort_session_execution(db, session.id)
                    return
                for event in drain():
                    if hasattr(event, "to_sse"):
                        yield event.to_sse()
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
            if await request.is_disconnected():
                _abort_session_execution(db, session.id)
                return
            for event in drain():
                if hasattr(event, "to_sse"):
                    yield event.to_sse()
            try:
                db.commit()
            except Exception:
                logger.exception("Failed to commit session events")
            yield "data: [DONE]\n\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    responses = [
        response
        async for response in orchestrator.stream_responses(
            user_message=payload.message,
            output_dir=settings.output_dir,
            history=history,
            trigger_interview=trigger_interview,
            generate_now=payload.generate_now,
        )
    ]
    final = responses[-1] if responses else None
    assistant_message = final.message if final else ""
    if assistant_message:
        message_service.add_message(session.id, "assistant", assistant_message)
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


@router.get("/stream")
async def stream(
    request: Request,
    session_id: Optional[str] = None,
    message: Optional[str] = None,
    interview: Optional[bool] = None,
    db: DbSession = Depends(_get_db_session),
):
    settings = get_settings()

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

        emitter = EventEmitter(session_id=session.id, event_store=EventStoreService(db))
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
        orchestrator = AgentOrchestrator(db, session, event_emitter=emitter)
        start_tokens = _token_total(db, session.id)

        async def event_stream() -> AsyncGenerator[str, None]:
            final_message = ""
            index = 0

            def drain() -> list:
                nonlocal index
                events, index = emitter.events_since(index)
                return events

            async for response in orchestrator.stream_responses(
                user_message=message,
                output_dir=settings.output_dir,
                history=history,
                trigger_interview=trigger_interview,
                generate_now=False,
            ):
                if await request.is_disconnected():
                    _abort_session_execution(db, session.id)
                    return
                for event in drain():
                    if hasattr(event, "to_sse"):
                        yield event.to_sse()
                final_message = response.message or final_message
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

            if await request.is_disconnected():
                _abort_session_execution(db, session.id)
                return
            for event in drain():
                if hasattr(event, "to_sse"):
                    yield event.to_sse()
            if final_message:
                message_service.add_message(session.id, "assistant", final_message)
                db.commit()
            else:
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
    orchestrator = AgentOrchestrator(
        db,
        session,
        event_emitter=EventEmitter(session_id=session.id, event_store=EventStoreService(db)),
    )

    async def event_stream() -> AsyncGenerator[str, None]:
        async for event in orchestrator.stream(
            user_message="", output_dir=settings.output_dir, skip_interview=True
        ):
            if await request.is_disconnected():
                _abort_session_execution(db, session.id)
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
