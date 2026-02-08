import uuid

from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel
from app.db.utils import get_db, transaction_scope
from app.schemas.session_metadata import BuildStatus, SessionMetadataUpdate
from app.services.state_store import StateStoreService


def _create_session(database: Database, session_id: str) -> None:
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="State Session"))


def test_state_store_save_load_clear(tmp_path) -> None:
    db_path = tmp_path / "state_store.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)
    payload = {"nodes": {"a": 1}, "edges": []}

    with get_db(database) as session:
        service = StateStoreService(session)
        assert service.save_state(session_id, payload) is True
        session.commit()

    with get_db(database) as session:
        service = StateStoreService(session)
        assert service.load_state(session_id) == payload
        assert service.clear_state(session_id) is True
        session.commit()

    with get_db(database) as session:
        service = StateStoreService(session)
        assert service.load_state(session_id) is None


def test_state_store_update_metadata(tmp_path) -> None:
    db_path = tmp_path / "state_metadata.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)

    with get_db(database) as session:
        service = StateStoreService(session)
        updates = SessionMetadataUpdate(
            build_status=BuildStatus.BUILDING,
            build_artifacts={"pages": ["index"]},
        )
        metadata = service.update_metadata(session_id, updates)
        session.commit()

    assert metadata is not None
    assert metadata.build_status == BuildStatus.BUILDING
    assert metadata.build_artifacts == {"pages": ["index"]}
