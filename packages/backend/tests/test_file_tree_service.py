import uuid

from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel
from app.db.utils import get_db, transaction_scope
from app.services.file_tree import FileTreeService
from app.services.page import PageService
from app.services.page_version import PageVersionService
from app.services.product_doc import ProductDocService


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
