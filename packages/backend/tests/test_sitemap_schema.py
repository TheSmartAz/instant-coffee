import pytest

from app.schemas.sitemap import SitemapResult


def _build_valid_payload() -> dict:
    return {
        "pages": [
            {
                "title": "Home",
                "slug": "index",
                "purpose": "Landing",
                "sections": ["hero", "cta"],
                "required": True,
            }
        ],
        "nav": [{"slug": "index", "label": "Home", "order": 0}],
        "global_style": {
            "primary_color": "#123ABC",
            "secondary_color": "#DEF456",
            "font_family": "Inter",
            "font_size_base": "16px",
            "font_size_heading": "24px",
            "button_height": "44px",
            "spacing_unit": "8px",
            "border_radius": "8px",
        },
    }


def _validate(payload: dict) -> SitemapResult:
    if hasattr(SitemapResult, "model_validate"):
        return SitemapResult.model_validate(payload)
    return SitemapResult.parse_obj(payload)


def test_sitemap_schema_valid() -> None:
    result = _validate(_build_valid_payload())
    assert result.pages[0].slug == "index"


def test_sitemap_schema_invalid_page_count() -> None:
    payload = _build_valid_payload()
    payload["pages"] = []
    with pytest.raises(ValueError):
        _validate(payload)


def test_sitemap_schema_invalid_color() -> None:
    payload = _build_valid_payload()
    payload["global_style"]["primary_color"] = "red"
    with pytest.raises(ValueError):
        _validate(payload)
