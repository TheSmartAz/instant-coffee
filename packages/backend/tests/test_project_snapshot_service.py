import uuid

from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import (
    PageVersion,
    ProductDocHistory,
    ProjectSnapshot,
    Session as SessionModel,
    VersionSource,
)
from app.db.utils import get_db, transaction_scope
from app.services.page import PageService
from app.services.page_version import PageVersionService
from app.services.product_doc import ProductDocService
from app.services.project_snapshot import PinnedLimitExceeded, ProjectSnapshotService


def _create_session(database: Database, session_id: str) -> None:
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Snapshot Session"))


def _seed_project(database: Database, session_id: str) -> dict:
    with get_db(database) as session:
        product_doc = ProductDocService(session).create(
            session_id=session_id,
            content="doc v1",
            structured={
                "design_direction": {"style": "minimal"},
            },
        )
        page_service = PageService(session)
        home = page_service.create(session_id=session_id, title="Home", slug="home")
        about = page_service.create(session_id=session_id, title="About", slug="about")
        version_service = PageVersionService(session)
        home_v1 = version_service.create(home.id, "<html>home v1</html>")
        about_v1 = version_service.create(about.id, "<html>about v1</html>")
        product_doc_id = product_doc.id
        home_id = home.id
        about_id = about.id
        home_v1_id = home_v1.id
        about_v1_id = about_v1.id
        session.commit()
    return {
        "product_doc_id": product_doc_id,
        "home_id": home_id,
        "about_id": about_id,
        "home_v1_id": home_v1_id,
        "about_v1_id": about_v1_id,
    }


def test_create_snapshot_captures_doc_and_pages(tmp_path) -> None:
    db_path = tmp_path / "snapshots_create.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)
    _seed_project(database, session_id)

    with get_db(database) as session:
        service = ProjectSnapshotService(session)
        snapshot = service.create_snapshot(session_id, source=VersionSource.AUTO, label="First")
        snapshot_id = snapshot.id
        session.commit()

    with get_db(database) as session:
        snapshot = session.get(ProjectSnapshot, snapshot_id)
        assert snapshot is not None
        assert snapshot.snapshot_number == 1
        assert snapshot.label == "First"
        assert snapshot.source == VersionSource.AUTO
        assert snapshot.doc is not None
        assert snapshot.doc.content == "doc v1"
        assert snapshot.doc.structured.get("design_direction") == {"style": "minimal"}
        assert snapshot.doc.global_style == {}
        assert len(snapshot.pages) == 2
        html_by_slug = {page.slug: page.rendered_html for page in snapshot.pages}
        assert html_by_slug["home"] == "<html>home v1</html>"
        assert html_by_slug["about"] == "<html>about v1</html>"


def test_retention_releases_old_auto_snapshots(tmp_path) -> None:
    db_path = tmp_path / "snapshots_retention.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)
    _seed_project(database, session_id)

    with get_db(database) as session:
        service = ProjectSnapshotService(session)
        for _ in range(6):
            service.create_snapshot(session_id, source=VersionSource.AUTO)
        session.commit()

    with get_db(database) as session:
        service = ProjectSnapshotService(session)
        snapshots = service.get_snapshots(session_id, include_released=True)
        assert len(snapshots) == 6
        oldest = min(snapshots, key=lambda snap: snap.snapshot_number)
        assert oldest.is_released is True
        assert oldest.doc is not None
        assert oldest.doc.content is None
        assert all(page.rendered_html is None for page in oldest.pages)


def test_pin_limit_enforced(tmp_path) -> None:
    db_path = tmp_path / "snapshots_pin.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)
    _seed_project(database, session_id)

    with get_db(database) as session:
        service = ProjectSnapshotService(session)
        first = service.create_snapshot(session_id, source=VersionSource.AUTO)
        second = service.create_snapshot(session_id, source=VersionSource.AUTO)
        third = service.create_snapshot(session_id, source=VersionSource.AUTO)
        service.pin_snapshot(first.id)
        service.pin_snapshot(second.id)
        try:
            service.pin_snapshot(third.id)
        except PinnedLimitExceeded as exc:
            assert len(exc.current_pinned) == 2
        else:
            raise AssertionError("expected pin limit exceeded")
        session.commit()

    with get_db(database) as session:
        pinned = (
            session.query(ProjectSnapshot)
            .filter(ProjectSnapshot.session_id == session_id)
            .filter(ProjectSnapshot.is_pinned.is_(True))
            .all()
        )
        assert len(pinned) == 2


def test_rollback_creates_new_versions(tmp_path) -> None:
    db_path = tmp_path / "snapshots_rollback.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)
    seed = _seed_project(database, session_id)

    with get_db(database) as session:
        snapshot_service = ProjectSnapshotService(session)
        base_snapshot = snapshot_service.create_snapshot(session_id, source=VersionSource.AUTO)
        base_snapshot_id = base_snapshot.id
        base_snapshot_number = base_snapshot.snapshot_number

        doc_service = ProductDocService(session)
        doc = doc_service.get_by_session_id(session_id)
        assert doc is not None
        doc_service.update(doc.id, content="doc v2")

        page_version_service = PageVersionService(session)
        page_version_service.create(seed["home_id"], "<html>home v2</html>")
        session.commit()

    with get_db(database) as session:
        snapshot_service = ProjectSnapshotService(session)
        rollback_snapshot = snapshot_service.rollback_to_snapshot(session_id, base_snapshot_id)
        rollback_snapshot_id = rollback_snapshot.id
        session.commit()

    with get_db(database) as session:
        doc = ProductDocService(session).get_by_session_id(session_id)
        assert doc is not None
        assert doc.content == "doc v1"
        assert doc.version == 3

        histories = (
            session.query(ProductDocHistory)
            .filter(ProductDocHistory.product_doc_id == doc.id)
            .order_by(ProductDocHistory.version.desc())
            .all()
        )
        assert histories
        assert histories[0].version == doc.version
        assert histories[0].source == VersionSource.ROLLBACK

        versions = (
            session.query(PageVersion)
            .filter(PageVersion.page_id == seed["home_id"])
            .order_by(PageVersion.version.desc())
            .all()
        )
        assert versions[0].html == "<html>home v1</html>"

        rollback_snapshot = session.get(ProjectSnapshot, rollback_snapshot_id)
        assert rollback_snapshot is not None
        assert rollback_snapshot.source == VersionSource.ROLLBACK
        assert rollback_snapshot.snapshot_number == base_snapshot_number + 1
