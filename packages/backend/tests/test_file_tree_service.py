import uuid

from app.db.database import Database
from app.config import refresh_settings
from app.db.migrations import init_db
from app.db.models import Session as SessionModel
from app.db.utils import get_db, transaction_scope
from app.schemas.session_metadata import BuildInfo, BuildStatus
from app.services.file_tree import FileTreeService
from app.services.page import PageService
from app.services.page_version import PageVersionService
from app.services.product_doc import ProductDocService
from app.services.state_store import StateStoreService


def _create_session(database, session_id: str) -> None:
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Files Session"))


def test_file_tree_service_builds_tree_and_content(tmp_path) -> None:
    db_path = tmp_path / "files_service.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)

    with get_db(database) as session:
        ProductDocService(session).create(
            session_id=session_id,
            content="# Product Doc",
            structured={"design_direction": {"color_preference": "#ff0000"}},
        )
        page_service = PageService(session)
        index_page = page_service.create(session_id=session_id, title="Index", slug="index")
        about_page = page_service.create(session_id=session_id, title="About", slug="about")
        version_service = PageVersionService(session)
        version_service.create(index_page.id, "<html>index</html>")
        version_service.create(about_page.id, "<html>about</html>")
        session.commit()

    with get_db(database) as session:
        service = FileTreeService(session)
        tree = service.get_tree(session_id)

        paths = [node.path for node in tree]
        assert "index.html" in paths
        assert "assets" in paths
        assert "pages" in paths
        assert "product-doc.md" in paths

        pages_node = next(node for node in tree if node.path == "pages")
        assert pages_node.children is not None
        assert pages_node.children[0].path == "pages/about.html"

        css_content = service.get_file_content(session_id, "assets/site.css")
        assert css_content is not None
        assert css_content.language == "css"
        assert "--primary-color: #FF0000;" in css_content.content

        html_content = service.get_file_content(session_id, "index.html")
        assert html_content is not None
        assert html_content.language == "html"
        assert "index" in html_content.content
        assert "href=\"assets/site.css\"" in html_content.content

        about_html = service.get_file_content(session_id, "pages/about.html")
        assert about_html is not None
        assert "href=\"../assets/site.css\"" in about_html.content

        missing = service.get_file_content(session_id, "pages/missing.html")
        assert missing is None


def test_file_tree_service_minimal_tree(tmp_path) -> None:
    db_path = tmp_path / "files_empty.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)

    with get_db(database) as session:
        service = FileTreeService(session)
        tree = service.get_tree(session_id)
        paths = [node.path for node in tree]
        assert "index.html" in paths
        assert "assets" in paths


def test_file_tree_service_exposes_non_html_workspace_files(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "files_workspace.db"
    output_dir = tmp_path / "output"
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    refresh_settings()
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)
    workspace = output_dir / session_id / "src"
    workspace.mkdir(parents=True)
    (workspace / "App.tsx").write_text("export function App() { return null }\n", encoding="utf-8")
    (output_dir / session_id / "index.html").write_text("<html>generated</html>", encoding="utf-8")

    with get_db(database) as session:
        service = FileTreeService(session)
        tree = service.get_tree(session_id)
        workspace_node = next(node for node in tree if node.path == "workspace")
        assert workspace_node.children is not None
        src_node = next(node for node in workspace_node.children if node.path == "workspace/src")
        assert src_node.children is not None
        assert src_node.children[0].path == "workspace/src/App.tsx"

        content = service.get_file_content(session_id, "workspace/src/App.tsx")
        assert content is not None
        assert content.language == "tsx"
        assert "export function App" in content.content
        assert service.get_file_content(session_id, "workspace/index.html") is None

    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    refresh_settings()


def test_file_tree_service_reads_dist_html_when_page_versions_empty(tmp_path) -> None:
    db_path = tmp_path / "files_dist.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)

    dist_dir = tmp_path / "dist-output"
    (dist_dir / "pages" / "about").mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text("<html><body>Dist index</body></html>", encoding="utf-8")
    (dist_dir / "pages" / "about" / "index.html").write_text(
        "<html><body>Dist about</body></html>",
        encoding="utf-8",
    )

    with get_db(database) as session:
        page_service = PageService(session)
        page_service.create(session_id=session_id, title="Index", slug="index")
        page_service.create(session_id=session_id, title="About", slug="about")
        StateStoreService(session).update_build_info(
            session_id,
            BuildInfo(
                status=BuildStatus.SUCCESS,
                pages=["index.html", "pages/about/index.html"],
                dist_path=str(dist_dir),
            ),
        )
        session.commit()

    with get_db(database) as session:
        service = FileTreeService(session)

        tree = service.get_tree(session_id)
        index_node = next(node for node in tree if node.path == "index.html")
        assert index_node.size and index_node.size > 0

        pages_node = next(node for node in tree if node.path == "pages")
        assert pages_node.children is not None
        about_node = next(node for node in pages_node.children if node.path == "pages/about.html")
        assert about_node.size and about_node.size > 0

        index_content = service.get_file_content(session_id, "index.html")
        assert index_content is not None
        assert "Dist index" in index_content.content

        about_content = service.get_file_content(session_id, "pages/about.html")
        assert about_content is not None
        assert "Dist about" in about_content.content
