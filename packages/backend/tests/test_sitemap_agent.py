from app.agents.sitemap import SitemapAgent
from app.config import Settings


def _make_agent() -> SitemapAgent:
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    return SitemapAgent(None, "session-1", settings)


def test_normalize_payload_adds_index() -> None:
    agent = _make_agent()
    structured = {
        "project_name": "Test",
        "pages": [{"title": "About", "slug": "about", "sections": ["story"]}],
    }
    payload = {
        "pages": [{"title": "About", "slug": "about", "sections": ["story"]}],
        "global_style": {"primary_color": "#123ABC", "font_family": "Test"},
    }
    normalized = agent._normalize_payload(
        payload=payload,
        structured=structured,
        design_direction={},
        multi_page=True,
    )
    slugs = [page["slug"] for page in normalized["pages"]]
    assert slugs[0] == "index"
    assert "about" in slugs
    index_page = next(page for page in normalized["pages"] if page["slug"] == "index")
    assert index_page["required"] is True


def test_normalize_payload_single_page() -> None:
    agent = _make_agent()
    structured = {
        "project_name": "Test",
        "pages": [
            {"title": "Home", "slug": "index", "sections": ["hero"]},
            {"title": "About", "slug": "about", "sections": ["story"]},
        ],
    }
    payload = {
        "pages": structured["pages"],
        "global_style": {"primary_color": "#123ABC", "font_family": "Test"},
    }
    normalized = agent._normalize_payload(
        payload=payload,
        structured=structured,
        design_direction={},
        multi_page=False,
    )
    slugs = [page["slug"] for page in normalized["pages"]]
    assert slugs == ["index"]
