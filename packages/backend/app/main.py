from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    build_router,
    chat_router,
    data_router,
    events_router,
    files_router,
    migrations_router,
    pages_router,
    plan_router,
    preview_router,
    product_doc_router,
    runs_router,
    session_abort_router,
    sessions_router,
    assets_router,
    schemas_router,
    settings_router,
    snapshots_router,
    tasks_router,
)
from .config import get_settings
from .db.data_migration_v04 import migrate_existing_sessions
from .db.migrations import init_db
from .db.database import get_database
from .services.app_data_store import close_app_data_store, initialize_app_data_store

logger = logging.getLogger(__name__)


def _resolve_cors_options() -> tuple[list[str], bool, list[str], list[str]]:
    settings = get_settings()
    allow_origins = settings.cors_allow_origins or ["*"]
    allow_credentials = settings.cors_allow_credentials

    if "*" in allow_origins and allow_credentials:
        logger.warning(
            "CORS_ALLOW_CREDENTIALS is true while CORS_ALLOW_ORIGINS contains '*'; forcing credentials=false"
        )
        allow_credentials = False

    return (
        allow_origins,
        allow_credentials,
        settings.cors_allow_methods or ["*"],
        settings.cors_allow_headers or ["*"],
    )


@asynccontextmanager
async def _lifespan(_: FastAPI):
    database = get_database()
    init_db(database)
    settings = get_settings()
    if settings.migrate_v04_on_startup:
        migrate_existing_sessions(database)
    await initialize_app_data_store()
    try:
        yield
    finally:
        await close_app_data_store()


def create_app() -> FastAPI:
    app = FastAPI(title="Instant Coffee API", lifespan=_lifespan)

    allow_origins, allow_credentials, allow_methods, allow_headers = _resolve_cors_options()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=allow_methods,
        allow_headers=allow_headers,
    )

    app.include_router(sessions_router)
    app.include_router(assets_router)
    app.include_router(build_router)
    app.include_router(chat_router)
    app.include_router(data_router)
    app.include_router(events_router)
    app.include_router(settings_router)
    app.include_router(tasks_router)
    app.include_router(plan_router)
    app.include_router(preview_router)
    app.include_router(session_abort_router)
    app.include_router(runs_router)
    app.include_router(migrations_router)
    app.include_router(pages_router)
    app.include_router(product_doc_router)
    app.include_router(files_router)
    app.include_router(snapshots_router)
    app.include_router(schemas_router)

    assets_dir = Path("~/.instant-coffee/sessions").expanduser()
    assets_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

__all__ = ["create_app", "app"]
