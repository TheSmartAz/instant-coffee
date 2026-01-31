from __future__ import annotations

import json
from typing import AsyncGenerator, Generator, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from ..agents.orchestrator import AgentOrchestrator
from ..config import get_settings
from ..db.models import Session as SessionModel
from ..db.utils import get_db
from ..events.emitter import EventEmitter
from ..services.message import MessageService
from ..services.session import SessionService
from .utils import build_preview_url

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(min_length=1)


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _accepts_sse(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/event-stream" in accept


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
    message_service.add_message(session.id, "user", payload.message)
    db.commit()

    emitter = EventEmitter(session_id=session.id)
    orchestrator = AgentOrchestrator(db, session, event_emitter=emitter)
    settings = get_settings()

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
            ):
                for event in drain():
                    if hasattr(event, "to_sse"):
                        yield event.to_sse()
                data = json.dumps(response.to_payload(), ensure_ascii=False)
                yield f"data: {data}\n\n"
            for event in drain():
                if hasattr(event, "to_sse"):
                    yield event.to_sse()
            yield "data: [DONE]\n\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    responses = [
        response
        async for response in orchestrator.stream_responses(
            user_message=payload.message,
            output_dir=settings.output_dir,
            history=history,
        )
    ]
    final = responses[-1] if responses else None
    assistant_message = final.message if final else ""
    if assistant_message:
        message_service.add_message(session.id, "assistant", assistant_message)
        db.commit()

    payload = {
        "session_id": session.id,
        "message": assistant_message,
        "preview_url": build_preview_url(request, session.id),
        "preview_html": final.preview_html if final else None,
    }
    return JSONResponse(payload)


@router.get("/stream")
async def stream(
    request: Request,
    session_id: Optional[str] = None,
    message: Optional[str] = None,
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
        message_service.add_message(session.id, "user", message)
        db.commit()

        emitter = EventEmitter(session_id=session.id)
        orchestrator = AgentOrchestrator(db, session, event_emitter=emitter)
        preview_url = build_preview_url(request, session.id)

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
            ):
                for event in drain():
                    if hasattr(event, "to_sse"):
                        yield event.to_sse()
                final_message = response.message or final_message
                payload = response.to_payload()
                payload["preview_url"] = preview_url
                data = json.dumps(payload, ensure_ascii=False)
                yield f"data: {data}\n\n"

            for event in drain():
                if hasattr(event, "to_sse"):
                    yield event.to_sse()
            if final_message:
                message_service.add_message(session.id, "assistant", final_message)
                db.commit()
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID required")

    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    orchestrator = AgentOrchestrator(db, session, event_emitter=EventEmitter(session_id=session.id))

    async def event_stream() -> AsyncGenerator[str, None]:
        async for event in orchestrator.stream(
            user_message="", output_dir=settings.output_dir, skip_interview=True
        ):
            if hasattr(event, "to_sse"):
                yield event.to_sse()
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


__all__ = ["router"]
