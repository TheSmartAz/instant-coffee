import asyncio
import uuid

from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import ProductDocStatus, Session as SessionModel
from app.db.utils import get_db, transaction_scope
from app.services.export import ExportService
from app.services.page import PageService
from app.services.page_version import PageVersionService
from app.services.product_doc import ProductDocService
from app.utils.style import build_site_css


def _create_session(database, session_id: str) -> None:
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Export Session"))


def test_export_service_multi_page(tmp_path) -> None:
    db_path = tmp_path / "export.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)

    with get_db(database) as session:
        ProductDocService(session).create(
            session_id=session_id,
            content="# Product Doc",
            structured={
                "design_direction": {"color_preference": "#1e88e5"},
            },
            status=ProductDocStatus.CONFIRMED,
        )

        page_service = PageService(session)
        index_page = page_service.create(session_id=session_id, title="Index", slug="index")
        about_page = page_service.create(session_id=session_id, title="About", slug="about")
        page_service.create(session_id=session_id, title="Missing", slug="missing")

        site_css = build_site_css({"primary_color": "#1e88e5"}, {"color_preference": "#1e88e5"})
        index_html = (
            f"<html><head><style>{site_css}</style></head>"
            "<body><a href=\"pages/about.html\">About</a></body></html>"
        )
        about_html = (
            f"<html><head><style>{site_css}</style></head>"
            "<body><a href=\"pages/index.html\">Home</a></body></html>"
        )
        version_service = PageVersionService(session)
        version_service.create(index_page.id, index_html)
        version_service.create(about_page.id, about_html)
        session.commit()

    with get_db(database) as session:
        service = ExportService(session)
        result = asyncio.run(
            service.export_session(
                session_id=session_id,
                output_dir=tmp_path,
                global_style={"primary_color": "#1e88e5", "font_family": "Noto Sans"},
            )
        )
        assert result.success is True

        export_dir = result.export_dir
        assert (export_dir / "index.html").exists()
        assert (export_dir / "pages/about.html").exists()
        assert (export_dir / "assets/site.css").exists()
        assert (export_dir / "product-doc.md").exists()
        assert (export_dir / "export_manifest.json").exists()

        manifest = result.manifest
        assert manifest["version"] == "1.0"
        assert manifest["product_doc"]["status"] == "confirmed"
        assert manifest["global_style"]["primary_color"] == "#1E88E5"
        asset_paths = {asset["path"] for asset in manifest["assets"]}
        assert "assets/site.css" in asset_paths

        status_by_slug = {page["slug"]: page for page in manifest["pages"]}
        assert status_by_slug["index"]["status"] == "success"
        assert status_by_slug["index"]["path"] == "index.html"
        assert status_by_slug["about"]["status"] == "success"
        assert status_by_slug["about"]["path"] == "pages/about.html"
        assert status_by_slug["missing"]["status"] == "failed"
        assert status_by_slug["missing"]["error"] == "missing_page_version"

        index_content = (export_dir / "index.html").read_text(encoding="utf-8")
        assert "href=\"pages/about.html\"" in index_content
        assert "assets/site.css" in index_content

        about_content = (export_dir / "pages/about.html").read_text(encoding="utf-8")
        assert "href=\"../index.html\"" in about_content
        assert "../assets/site.css" in about_content

        manifest_path = export_dir / "export_manifest.json"
        manifest_content = manifest_path.read_text(encoding="utf-8")
        assert "\"exported_at\"" in manifest_content
