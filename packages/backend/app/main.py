from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    chat_router,
    events_router,
    files_router,
    migrations_router,
    pages_router,
    plan_router,
    product_doc_router,
    session_abort_router,
    sessions_router,
    settings_router,
    snapshots_router,
    tasks_router,
)
from .config import get_settings
from .db.data_migration_v04 import migrate_existing_sessions
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
        database = get_database()
        init_db(database)
        settings = get_settings()
        if settings.migrate_v04_on_startup:
            migrate_existing_sessions(database)

    app.include_router(sessions_router)
    app.include_router(chat_router)
    app.include_router(events_router)
    app.include_router(settings_router)
    app.include_router(tasks_router)
    app.include_router(plan_router)
    app.include_router(session_abort_router)
    app.include_router(migrations_router)
    app.include_router(pages_router)
    app.include_router(product_doc_router)
    app.include_router(files_router)
    app.include_router(snapshots_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

__all__ = ["create_app", "app"]
