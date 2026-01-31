from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    chat_router,
    plan_router,
    session_abort_router,
    sessions_router,
    settings_router,
    tasks_router,
)
from .db.migrations import init_db
from .db.database import get_database


def create_app() -> FastAPI:
    app = FastAPI(title="Instant Coffee API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        init_db(get_database())

    app.include_router(sessions_router)
    app.include_router(chat_router)
    app.include_router(settings_router)
    app.include_router(tasks_router)
    app.include_router(plan_router)
    app.include_router(session_abort_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

__all__ = ["create_app", "app"]
