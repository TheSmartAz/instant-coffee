import uuid

from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import PageVersion, Session as SessionModel
from app.db.utils import get_db, transaction_scope
from app.services.page import PageService
from app.services.product_doc import ProductDocService
from app.services.review import ReviewInput, ReviewPageInput, ReviewService


def _create_session(database: Database, session_id: str) -> None:
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Test Session"))


def test_review_passes_when_doc_pages_html_and_build_artifacts_align() -> None:
    result = ReviewService().review(
        {
            "product_doc_content": "## Pages\n- Home (/)\n- Search (/search)",
            "product_doc_status": "confirmed",
            "pages": [
                {"slug": "index", "title": "Home", "html": "<html><body>Home</body></html>"},
                {"slug": "search", "title": "Search", "html": "<main>Search</main>"},
            ],
            "build": {
                "status": "success",
                "pages": ["index.html", "search.html"],
                "log_summary": "Build completed successfully",
            },
        }
    )

    assert result.verdict == "pass"
    assert result.passed is True
    assert result.issues == []
    assert result.summary["generated_pages"] == ["index", "search"]


def test_review_fails_for_missing_expected_page_and_failed_build() -> None:
    result = ReviewService().review(
        ReviewInput(
            product_doc_content="## Pages\n- Home (/)\n- Search (/search)",
            product_doc_status="confirmed",
            pages=[
                ReviewPageInput(
                    slug="index",
                    title="Home",
                    html="<html><body>{{ headline }}</body></html>",
                )
            ],
            build={
                "status": "failed",
                "pages": ["index.html"],
                "error": "npm run build failed",
                "log_summary": "Error: missing module",
            },
        )
    )

    assert result.verdict == "fail"
    codes = [issue.code for issue in result.issues]
    assert "expected_page_missing" in codes
    assert "page_placeholder_leftover" in codes
    assert "build_failed" in codes
    assert "build_error_present" in codes
    assert "build_log_error" in codes


def test_review_maps_nested_index_html_build_paths_to_parent_slug() -> None:
    result = ReviewService().review(
        {
            "product_doc_content": "## Pages\n- About (/about)",
            "product_doc_status": "confirmed",
            "pages": [
                {"slug": "about", "title": "About", "html": "<main>About</main>"},
            ],
            "build": {
                "status": "success",
                "pages": ["pages/about/index.html"],
                "log_summary": "Build completed successfully",
            },
        }
    )

    assert result.verdict == "pass"
    assert result.summary["generated_pages"] == ["about"]


def test_review_fails_when_successful_build_has_no_artifacts_for_generated_pages() -> None:
    result = ReviewService().review(
        {
            "product_doc_content": "## Pages\n- Home (/)",
            "product_doc_status": "confirmed",
            "pages": [
                {"slug": "index", "title": "Home", "html": "<html><body>Home</body></html>"},
            ],
            "build": {
                "status": "success",
                "pages": [],
                "log_summary": "Build completed successfully",
            },
        }
    )

    assert result.verdict == "fail"
    codes = [issue.code for issue in result.issues]
    assert codes == ["build_artifact_missing"]
    assert result.issues[0].subject == "index"


def test_review_session_reads_product_doc_pages_and_build_metadata(tmp_path) -> None:
    db_path = tmp_path / "review.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    _create_session(database, session_id)

    with get_db(database) as session:
        ProductDocService(session).create(
            session_id=session_id,
            content="## Pages\n- Home (/)\n- Profile (/profile)",
            structured={},
            status="confirmed",
        )
        page = PageService(session).create(
            session_id=session_id,
            title="Home",
            slug="index",
        )
        version = PageVersion(
            page_id=page.id,
            version=1,
            html="<html><body>Home</body></html>",
        )
        session.add(version)
        session.flush()
        page.current_version_id = version.id
        metadata = session.get(SessionModel, session_id)
        metadata.build_status = "success"
        metadata.build_artifacts = {"pages": ["index.html"]}
        session.commit()

    with get_db(database) as session:
        result = ReviewService(session).review_session(session_id)

    assert result.verdict == "fail"
    codes = [issue.code for issue in result.issues]
    assert codes == ["expected_page_missing"]
    assert result.summary["expected_pages"] == ["index", "profile"]
    assert result.summary["generated_pages"] == ["index"]
