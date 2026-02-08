from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Iterable

from bs4 import BeautifulSoup, Doctype, Tag

VIEWPORT_CONTENT = "width=device-width, initial-scale=1, viewport-fit=cover, maximum-scale=1"
MOBILE_SHELL_STYLE_ID = "mobile-shell"

MOBILE_SHELL_CSS = """
* { box-sizing: border-box; }
html, body {
  margin: 0;
  padding: 0;
  min-height: 100dvh;
  -webkit-font-smoothing: antialiased;
}
#app.page {
  max-width: min(430px, 100%);
  width: 100%;
  margin: 0 auto;
  min-height: 100dvh;
  overflow-x: hidden;
  position: relative;
}
::-webkit-scrollbar { display: none; }
* { scrollbar-width: none; }
button, a, [role="button"] {
  min-height: 44px;
  touch-action: manipulation;
}
""".strip()

_VIEWPORT_TOKENS = {
    "width=device-width",
    "initial-scale=1",
    "viewport-fit=cover",
    "maximum-scale=1",
}
_MIN_HEIGHT_RE = re.compile(r"(?:min-height|height)\s*:\s*([0-9.]+)px", re.IGNORECASE)
_TOUCH_TARGET_RE = re.compile(r"min-height\s*:\s*44px", re.IGNORECASE)


@dataclass(frozen=True)
class MobileValidationRule:
    id: str
    description: str
    check: Callable[[BeautifulSoup], bool]
    auto_fix: bool


def ensure_mobile_shell(html: str) -> str:
    """
    Ensure generated HTML includes the mobile shell requirements:
    - viewport meta
    - #app.page container
    - injected mobile CSS
    """
    soup = BeautifulSoup(html or "", "html.parser")
    head, body = _ensure_head_and_body(soup)

    _ensure_viewport(soup, head)
    _ensure_app_container(soup, body)
    _ensure_mobile_shell_style(soup, head)

    return str(soup)


def validate_mobile_shell(html: str) -> dict:
    soup = BeautifulSoup(html or "", "html.parser")
    results = []
    for rule in MOBILE_VALIDATION_RULES:
        passed = False
        try:
            passed = bool(rule.check(soup))
        except Exception:
            passed = False
        results.append(
            {
                "id": rule.id,
                "description": rule.description,
                "passed": passed,
                "auto_fix": rule.auto_fix,
            }
        )
    return {"passed": all(item["passed"] for item in results), "rules": results}


def _ensure_head_and_body(soup: BeautifulSoup) -> tuple[Tag, Tag]:
    html_tag = soup.find("html")
    if html_tag is None:
        html_tag = soup.new_tag("html")
        soup.append(html_tag)

    head = soup.find("head")
    if head is None:
        head = soup.new_tag("head")
        html_tag.insert(0, head)
    elif head.parent is not html_tag:
        head.extract()
        html_tag.insert(0, head)

    body = soup.find("body")
    if body is None:
        body = soup.new_tag("body")
        html_tag.append(body)
    elif body.parent is not html_tag:
        body.extract()
        html_tag.append(body)

    for child in list(soup.contents):
        if child in {html_tag, head, body}:
            continue
        if isinstance(child, Doctype):
            continue
        if getattr(child, "name", None) == "html":
            continue
        body.append(child.extract())

    return head, body


def _ensure_viewport(soup: BeautifulSoup, head: BeautifulSoup) -> None:
    viewport = soup.find("meta", attrs={"name": "viewport"})
    if viewport is None:
        viewport = soup.new_tag("meta")
        viewport["name"] = "viewport"
        head.insert(0, viewport)
    viewport["content"] = VIEWPORT_CONTENT


def _ensure_app_container(soup: BeautifulSoup, body: BeautifulSoup) -> None:
    app_container = soup.find(id="app")
    if app_container is None:
        app_container = soup.new_tag("div")
        app_container["id"] = "app"
        app_container["class"] = ["page"]
        for child in list(body.contents):
            app_container.append(child.extract())
        body.append(app_container)
        return

    classes = app_container.get("class", [])
    if isinstance(classes, str):
        classes = [classes]
    if "page" not in classes:
        app_container["class"] = list(classes) + ["page"]


def _ensure_mobile_shell_style(soup: BeautifulSoup, head: BeautifulSoup) -> None:
    style_tag = soup.find("style", id=MOBILE_SHELL_STYLE_ID)
    if style_tag is None:
        style_tag = soup.new_tag("style")
        style_tag["id"] = MOBILE_SHELL_STYLE_ID
        head.append(style_tag)
    style_tag.string = MOBILE_SHELL_CSS


def _normalize_viewport_tokens(content: str) -> set[str]:
    items = [item.strip().lower() for item in (content or "").split(",")]
    return {item for item in items if item}


def _check_viewport(soup: BeautifulSoup) -> bool:
    viewport = soup.find("meta", attrs={"name": "viewport"})
    if viewport is None:
        return False
    content = viewport.get("content") or ""
    tokens = _normalize_viewport_tokens(content)
    return _VIEWPORT_TOKENS.issubset(tokens)


def _check_app_container(soup: BeautifulSoup) -> bool:
    app = soup.find(id="app")
    if app is None:
        return False
    classes = app.get("class", [])
    if isinstance(classes, str):
        classes = [classes]
    return "page" in classes


def _check_max_width(soup: BeautifulSoup) -> bool:
    style_tag = soup.find("style", id=MOBILE_SHELL_STYLE_ID)
    if style_tag and "max-width" in (style_tag.text or ""):
        return True
    app = soup.find(id="app")
    if app is None:
        return False
    style = app.get("style") or ""
    return "max-width" in style


def _extract_min_height(style: str) -> Iterable[float]:
    for match in _MIN_HEIGHT_RE.finditer(style or ""):
        try:
            yield float(match.group(1))
        except (TypeError, ValueError):
            continue


def check_touch_targets(soup: BeautifulSoup) -> bool:
    style_tag = soup.find("style", id=MOBILE_SHELL_STYLE_ID)
    if style_tag and _TOUCH_TARGET_RE.search(style_tag.text or ""):
        return True

    targets = soup.select("button, a, [role='button']")
    if not targets:
        return True

    for target in targets:
        style = target.get("style") or ""
        heights = list(_extract_min_height(style))
        if not heights or max(heights) < 44:
            return False
    return True


MOBILE_VALIDATION_RULES = [
    MobileValidationRule(
        id="viewport",
        description="Viewport meta must include mobile settings",
        check=_check_viewport,
        auto_fix=True,
    ),
    MobileValidationRule(
        id="app_container",
        description="Must include #app.page container",
        check=_check_app_container,
        auto_fix=True,
    ),
    MobileValidationRule(
        id="max_width",
        description="#app must enforce max-width constraints",
        check=_check_max_width,
        auto_fix=True,
    ),
    MobileValidationRule(
        id="touch_targets",
        description="Interactive elements must be at least 44px tall",
        check=check_touch_targets,
        auto_fix=False,
    ),
]


__all__ = [
    "MOBILE_SHELL_CSS",
    "MOBILE_SHELL_STYLE_ID",
    "MOBILE_VALIDATION_RULES",
    "VIEWPORT_CONTENT",
    "check_touch_targets",
    "ensure_mobile_shell",
    "validate_mobile_shell",
]
