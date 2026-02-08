import asyncio
import uuid

from app.config import refresh_settings
from app.db.database import reset_database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel
from app.db.utils import get_db
from app.events.emitter import EventEmitter
from app.events.types import EventType
from app.graph.nodes.aesthetic_scorer import aesthetic_scorer_node
from app.graph.nodes.generate import generate_node


def _init_db(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "langgraph_aesthetic_flow.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost")
    monkeypatch.setenv("DEFAULT_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("DMX_API_KEY", "")
    monkeypatch.setenv("DMXAPI_API_KEY", "")
    refresh_settings()
    reset_database()
    init_db()


def test_langgraph_page_sync_and_aesthetic_event(tmp_path, monkeypatch) -> None:
    _init_db(tmp_path, monkeypatch)
    session_id = uuid.uuid4().hex
    with get_db() as db:
        db.add(SessionModel(id=session_id, title="LangGraph Flow"))
        db.commit()

    emitter = EventEmitter(session_id=session_id)
    state = {
        "session_id": session_id,
        "component_registry": {"components": [{"id": "button-primary"}], "tokens": {}},
        "page_schemas": [
            {
                "slug": "index",
                "title": "Home",
                "layout": "default",
                "components": [
                    {
                        "id": "button-primary",
                        "key": "cta-1",
                        "props": {"label": {"type": "static", "value": "Start"}},
                    }
                ],
            }
        ],
        "product_doc": {"product_type": "landing"},
    }

    state = asyncio.run(generate_node(state, event_emitter=emitter))
    state = asyncio.run(aesthetic_scorer_node(state, event_emitter=emitter))

    event_types = [event.type for event in emitter.get_events()]
    assert EventType.PAGE_CREATED in event_types
    assert EventType.AESTHETIC_SCORE in event_types
