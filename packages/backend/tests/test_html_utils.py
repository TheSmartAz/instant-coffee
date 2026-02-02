from app.utils.html import (
    build_nav_html,
    ensure_css_link,
    ensure_nav_html,
    normalize_internal_links,
    rewrite_internal_links_for_export,
)


def test_build_nav_html_active_and_links() -> None:
    nav = [
        {"slug": "index", "label": "Home", "order": 0},
        {"slug": "about", "label": "About", "order": 1},
    ]
    html = build_nav_html(nav, current_slug="about")
    assert "class=\"site-nav\"" in html
    assert "href=\"index.html\"" in html
    assert "href=\"pages/about.html\"" in html
    assert "nav-link active" in html


def test_normalize_internal_links_and_warnings() -> None:
    html = (
        "<a href=\"about\">About</a>"
        "<a href=\"pages/contact.html\">Contact</a>"
        "<a href=\"#section\">Anchor</a>"
        "<a href=\"https://example.com\">External</a>"
        "<a href=\"assets/logo.png\">Logo</a>"
        "<a href=\"pricing\">Pricing</a>"
    )
    updated, warnings = normalize_internal_links(html, all_pages=["index", "about", "contact"])
    assert "href=\"pages/about.html\"" in updated
    assert "href=\"pages/contact.html\"" in updated
    assert "href=\"#section\"" in updated
    assert "href=\"https://example.com\"" in updated
    assert "href=\"assets/logo.png\"" in updated
    assert warnings == ["pricing"]


def test_ensure_nav_html_inserts_into_body() -> None:
    html = "<html><body><main>Content</main></body></html>"
    nav_html = "<nav class=\"site-nav\">Nav</nav>"
    updated = ensure_nav_html(html, nav_html)
    assert "site-nav" in updated
    assert updated.index("site-nav") < updated.index("Content")


def test_ensure_css_link_in_head() -> None:
    html = "<html><head></head><body></body></html>"
    updated = ensure_css_link(html, "assets/site.css")
    assert "assets/site.css" in updated


def test_rewrite_internal_links_for_export_index_page() -> None:
    html = (
        "<a href=\"about.html\">About</a>"
        "<a href=\"index.html#top\">Home</a>"
        "<a href=\"/contact\">Contact</a>"
        "<a href=\"https://example.com\">External</a>"
    )
    updated, warnings = rewrite_internal_links_for_export(
        html,
        current_slug="index",
        all_pages=["index", "about", "contact"],
    )
    assert "href=\"pages/about.html\"" in updated
    assert "href=\"index.html#top\"" in updated
    assert "href=\"pages/contact.html\"" in updated
    assert "href=\"https://example.com\"" in updated
    assert warnings == []


def test_rewrite_internal_links_for_export_nested_page() -> None:
    html = (
        "<a href=\"pages/index.html\">Home</a>"
        "<a href=\"pages/about.html?x=1\">About</a>"
        "<a href=\"pricing\">Pricing</a>"
    )
    updated, warnings = rewrite_internal_links_for_export(
        html,
        current_slug="about",
        all_pages=["index", "about"],
    )
    assert "href=\"../index.html\"" in updated
    assert "href=\"about.html?x=1\"" in updated
    assert warnings == ["pricing"]
