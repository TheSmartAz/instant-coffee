from bs4 import BeautifulSoup

from app.services.mobile_shell import (
    MOBILE_SHELL_STYLE_ID,
    VIEWPORT_CONTENT,
    check_touch_targets,
    ensure_mobile_shell,
    validate_mobile_shell,
)


def test_ensure_mobile_shell_injects_viewport_app_and_style() -> None:
    html = "<html><head><title>Test</title></head><body><main>Hi</main></body></html>"
    updated = ensure_mobile_shell(html)
    soup = BeautifulSoup(updated, "html.parser")

    viewport = soup.find("meta", attrs={"name": "viewport"})
    assert viewport is not None
    assert viewport.get("content") == VIEWPORT_CONTENT

    app = soup.find(id="app")
    assert app is not None
    assert "page" in (app.get("class") or [])
    assert app.find("main") is not None

    style = soup.find("style", id=MOBILE_SHELL_STYLE_ID)
    assert style is not None
    assert "max-width" in (style.text or "")


def test_ensure_mobile_shell_creates_structure_when_missing() -> None:
    html = "<div>Hi</div>"
    updated = ensure_mobile_shell(html)
    soup = BeautifulSoup(updated, "html.parser")

    assert soup.find("html") is not None
    assert soup.find("head") is not None
    assert soup.find("body") is not None

    app = soup.find(id="app")
    assert app is not None
    assert app.find("div") is not None


def test_validate_mobile_shell_passes_after_fix() -> None:
    raw = "<html><body><button>Go</button></body></html>"
    fixed = ensure_mobile_shell(raw)
    report = validate_mobile_shell(fixed)

    assert report["passed"] is True
    assert all(rule["passed"] for rule in report["rules"])


def test_validate_mobile_shell_fails_without_viewport_or_max_width() -> None:
    html = "<html><head></head><body><div id=\"app\" class=\"page\"></div></body></html>"
    report = validate_mobile_shell(html)
    rules = {rule["id"]: rule for rule in report["rules"]}

    assert report["passed"] is False
    assert rules["viewport"]["passed"] is False
    assert rules["max_width"]["passed"] is False


def test_check_touch_targets_inline_styles() -> None:
    html = "<html><body><a style=\"min-height: 44px\">Link</a></body></html>"
    soup = BeautifulSoup(html, "html.parser")
    assert check_touch_targets(soup) is True

    html_missing = "<html><body><a>Link</a></body></html>"
    soup_missing = BeautifulSoup(html_missing, "html.parser")
    assert check_touch_targets(soup_missing) is False
