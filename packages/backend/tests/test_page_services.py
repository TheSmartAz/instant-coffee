import uuid

from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import Page, PageVersion, Session as SessionModel
from app.db.utils import get_db, transaction_scope
from app.events.emitter import EventEmitter
from app.schemas.page import PageCreate
from app.services.page import PageService
from app.services.page_version import PageVersionReleasedError, PageVersionService


def _create_session(database, session_id: str) -> None:
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Test Session"))


def test_page_service_create_list_update_delete(tmp_path) -> None:
    db_path = tmp_path / "pages.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)

    with get_db(database) as session:
        service = PageService(session)
        page_b = service.create(
            session_id=session_id,
            title="Page B",
            slug="page-b",
            description="",
            order_index=2,
        )
        page_a = service.create(
            session_id=session_id,
            title="Page A",
            slug="page-a",
            description="",
            order_index=1,
        )
        page_a_id = page_a.id
        page_b_id = page_b.id
        session.commit()

    with get_db(database) as session:
        service = PageService(session)
        pages = service.list_by_session(session_id)
        assert [page.id for page in pages] == [page_a_id, page_b_id]

        updated = service.update(page_a_id, title="Updated", order_index=3)
        session.commit()
        assert updated is not None
        assert updated.title == "Updated"
        assert updated.order_index == 3

    with get_db(database) as session:
        service = PageService(session)
        assert service.delete(page_b_id) is True
        assert service.delete("missing") is False
        session.commit()

        remaining = service.list_by_session(session_id)
        assert len(remaining) == 1
        assert remaining[0].id == page_a_id


def test_page_service_slug_validation_and_conflicts(tmp_path) -> None:
    db_path = tmp_path / "slug.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)

    with get_db(database) as session:
        service = PageService(session)
        try:
            service.create(session_id=session_id, title="Bad", slug="Bad Slug")
        except ValueError as exc:
            assert "slug" in str(exc).lower()
        else:
            raise AssertionError("expected slug validation error")

        page_one = service.create(session_id=session_id, title="One", slug="one")
        page_two = service.create(session_id=session_id, title="Two", slug="two")
        page_two_id = page_two.id
        session.commit()

    with get_db(database) as session:
        service = PageService(session)
        try:
            service.update(page_two_id, slug="one")
        except ValueError as exc:
            assert "slug" in str(exc).lower()
        else:
            raise AssertionError("expected slug conflict error")

        page_two = service.get_by_id(page_two_id)
        assert page_two is not None
        assert page_two.slug == "two"


def test_page_service_create_batch_atomic(tmp_path) -> None:
    db_path = tmp_path / "batch.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)

    with get_db(database) as session:
        service = PageService(session)
        try:
            service.create_batch(
                session_id,
                [
                    PageCreate(title="A", slug="dup", description="", order_index=0),
                    PageCreate(title="B", slug="dup", description="", order_index=1),
                ],
            )
        except ValueError as exc:
            assert "duplicate" in str(exc).lower()
        else:
            raise AssertionError("expected duplicate slug error")
        session.commit()

    with get_db(database) as session:
        service = PageService(session)
        assert service.list_by_session(session_id) == []

        service.create(session_id=session_id, title="Home", slug="home")
        session.commit()

    with get_db(database) as session:
        service = PageService(session)
        try:
            service.create_batch(
                session_id,
                [
                    PageCreate(title="Home2", slug="home", description="", order_index=0),
                    PageCreate(title="About", slug="about", description="", order_index=1),
                ],
            )
        except ValueError as exc:
            assert "slug" in str(exc).lower()
        else:
            raise AssertionError("expected existing slug error")
        session.commit()

        pages = service.list_by_session(session_id)
        assert len(pages) == 1
        assert pages[0].slug == "home"


def test_page_version_service_create_and_preview(tmp_path) -> None:
    db_path = tmp_path / "versions.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)

    with get_db(database) as session:
        page = PageService(session).create(
            session_id=session_id,
            title="Index",
            slug="index",
        )
        page_id = page.id
        version_service = PageVersionService(session)
        v1 = version_service.create(page_id, "<html>v1</html>")
        v2 = version_service.create(page_id, "<html>v2</html>")
        v1_id = v1.id
        v2_id = v2.id
        session.commit()

    with get_db(database) as session:
        page = session.get(Page, page_id)
        assert page is not None
        assert page.current_version_id == v2_id

        version_service = PageVersionService(session)
        current = version_service.get_current(page_id)
        assert current is not None
        assert current.id == v2_id
        assert current.version == 2

        preview = version_service.preview_version(page_id, v1_id)
        session.commit()
        assert preview is not None
        assert preview.id == v1_id


def test_page_version_retention_prunes_old_versions(tmp_path) -> None:
    db_path = tmp_path / "retention.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)

    with get_db(database) as session:
        page = PageService(session).create(
            session_id=session_id,
            title="Index",
            slug="index",
        )
        page_id = page.id
        version_service = PageVersionService(session)
        for idx in range(7):
            version_service.create(page_id, f"<html>v{idx + 1}</html>")
        session.commit()

    with get_db(database) as session:
        versions = (
            session.query(PageVersion)
            .filter(PageVersion.page_id == page_id)
            .order_by(PageVersion.version.asc())
            .all()
        )
        assert len(versions) == 7
        released = [v for v in versions if v.is_released]
        kept = [v for v in versions if not v.is_released]
        assert len(released) == 2
        assert len(kept) == 5
        for version in released:
            assert version.html is None
            assert version.payload_pruned_at is not None

        service = PageVersionService(session)
        released_version = released[0]
        try:
            service.preview_version(page_id, released_version.id)
        except PageVersionReleasedError:
            pass
        else:
            raise AssertionError("expected released version to be non-previewable")


def test_page_version_preview_inlines_css(tmp_path) -> None:
    db_path = tmp_path / "preview.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)

    html = "<html><head><title>Test</title></head><body>Hi</body></html>"
    css = "body { color: red; }"

    with get_db(database) as session:
        page = PageService(session).create(
            session_id=session_id,
            title="Index",
            slug="index",
        )
        page_id = page.id
        PageVersionService(session).create(page_id, html)
        session.commit()

    with get_db(database) as session:
        service = PageVersionService(session)
        preview = service.build_preview(page_id, global_style_css=css)
        assert preview is not None
        _, rendered = preview
        assert "<style>" in rendered
        assert css in rendered
        assert rendered.index("<style>") < rendered.lower().index("</head>")


def test_page_service_delete_cascades_versions(tmp_path) -> None:
    db_path = tmp_path / "cascade.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)

    with get_db(database) as session:
        page = PageService(session).create(
            session_id=session_id,
            title="Index",
            slug="index",
        )
        page_id = page.id
        PageVersionService(session).create(page_id, "<html>v1</html>")
        session.commit()

    with get_db(database) as session:
        service = PageService(session)
        assert service.delete(page_id) is True
        session.commit()

    with get_db(database) as session:
        remaining_versions = (
            session.query(PageVersion)
            .filter(PageVersion.page_id == page_id)
            .all()
        )
        assert remaining_versions == []


def test_page_events_emitted(tmp_path) -> None:
    db_path = tmp_path / "events.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)

    emitter = EventEmitter(session_id=session_id)

    with get_db(database) as session:
        page_service = PageService(session, event_emitter=emitter)
        page = page_service.create(
            session_id=session_id,
            title="Index",
            slug="index",
        )
        version_service = PageVersionService(session, event_emitter=emitter)
        version_service.create(page.id, "<html>v1</html>")
        session.commit()

    events = emitter.get_events()
    assert len(events) == 3
    assert events[0].type.value == "page_created"
    assert events[1].type.value == "page_version_created"
    assert events[2].type.value == "page_preview_ready"
