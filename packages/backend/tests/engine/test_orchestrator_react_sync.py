import uuid

from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import PageVersion, Session as SessionModel
from app.db.utils import get_db, transaction_scope
from app.engine.orchestrator import EngineOrchestrator
from app.services.page import PageService
from app.services.page_version import PageVersionService


def _create_session(database: Database, session_id: str) -> None:
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Test Session"))


def test_react_page_sync_normalizes_ordinary_filenames(tmp_path) -> None:
    database = Database(f"sqlite:///{tmp_path / 'react-sync-slugs.db'}")
    init_db(database)
    session_id = uuid.uuid4().hex
    _create_session(database, session_id)

    workspace = tmp_path / "workspace"
    pages_dir = workspace / "src" / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "About Us.tsx").write_text(
        "export default function AboutUs() { return <main>About</main> }\n",
        encoding="utf-8",
    )
    (pages_dir / "Pricing_v2!.jsx").write_text(
        "export default function Pricing() { return <main>Pricing</main> }\n",
        encoding="utf-8",
    )

    with get_db(database) as db:
        session_record = db.get(SessionModel, session_id)
        assert session_record is not None
        synced = EngineOrchestrator(db, session_record)._sync_workspace_react_pages(str(workspace))
        db.commit()

        assert synced == ["about-us", "pricing-v2"]
        pages = PageService(db).list_by_session(session_id)
        assert [page.slug for page in pages] == ["about-us", "pricing-v2"]
        versions = db.query(PageVersion).order_by(PageVersion.version.asc()).all()
        assert len(versions) == 2
        assert all(version.html and "data-instant-coffee-source-snapshot=\"react\"" in version.html for version in versions)


def test_react_page_sync_creates_new_version_when_source_changes(tmp_path) -> None:
    database = Database(f"sqlite:///{tmp_path / 'react-sync-versions.db'}")
    init_db(database)
    session_id = uuid.uuid4().hex
    _create_session(database, session_id)

    workspace = tmp_path / "workspace"
    src_dir = workspace / "src"
    src_dir.mkdir(parents=True)
    app_path = src_dir / "App.tsx"
    app_path.write_text(
        "export default function App() { return <main>Initial</main> }\n",
        encoding="utf-8",
    )

    with get_db(database) as db:
        session_record = db.get(SessionModel, session_id)
        assert session_record is not None
        orchestrator = EngineOrchestrator(db, session_record)

        assert orchestrator._sync_workspace_react_pages(str(workspace)) == ["index"]
        page = PageService(db).get_by_slug(session_id, "index")
        assert page is not None
        first = PageVersionService(db).get_current(page.id)
        assert first is not None
        assert "Initial" in (first.html or "")

        assert orchestrator._sync_workspace_react_pages(str(workspace)) == ["index"]
        assert db.query(PageVersion).filter(PageVersion.page_id == page.id).count() == 1

        app_path.write_text(
            "export default function App() { return <main>Updated</main> }\n",
            encoding="utf-8",
        )
        assert orchestrator._sync_workspace_react_pages(str(workspace)) == ["index"]
        versions = (
            db.query(PageVersion)
            .filter(PageVersion.page_id == page.id)
            .order_by(PageVersion.version.asc())
            .all()
        )
        assert [version.version for version in versions] == [1, 2]
        assert "Updated" in (versions[-1].html or "")
        assert page.current_version_id == versions[-1].id


def test_react_page_sync_tracks_app_source_for_page_file_edits(tmp_path) -> None:
    database = Database(f"sqlite:///{tmp_path / 'react-sync-app-context.db'}")
    init_db(database)
    session_id = uuid.uuid4().hex
    _create_session(database, session_id)

    workspace = tmp_path / "workspace"
    src_dir = workspace / "src"
    pages_dir = src_dir / "pages"
    pages_dir.mkdir(parents=True)
    (src_dir / "App.tsx").write_text(
        "export default function App() { return <Router /> }\n",
        encoding="utf-8",
    )
    (pages_dir / "Home.tsx").write_text(
        "export default function Home() { return <main>Home</main> }\n",
        encoding="utf-8",
    )

    with get_db(database) as db:
        session_record = db.get(SessionModel, session_id)
        assert session_record is not None
        orchestrator = EngineOrchestrator(db, session_record)
        orchestrator._sync_workspace_react_pages(str(workspace))
        page = PageService(db).get_by_slug(session_id, "home")
        assert page is not None
        first = PageVersionService(db).get_current(page.id)
        assert first is not None
        assert "src/App.tsx" in (first.html or "")

        (src_dir / "App.tsx").write_text(
            "export default function App() { return <Router basename=\"/next\" /> }\n",
            encoding="utf-8",
        )
        orchestrator._sync_workspace_react_pages(str(workspace))

        assert db.query(PageVersion).filter(PageVersion.page_id == page.id).count() == 2
