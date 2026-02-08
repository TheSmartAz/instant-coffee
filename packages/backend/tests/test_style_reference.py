import pytest
from pydantic import ValidationError

from app.schemas.style_reference import StyleImage, StyleScope, StyleReference
from app.services.style_reference import normalize_style_tokens, tokens_to_global_style, StyleReferenceService


def _sample_tokens() -> dict:
    return {
        "colors": {
            "primary": "#112233",
            "accent": "#445566",
            "background": {
                "main": "#FFFFFF",
                "card": "#F9F9F9",
                "surface": "#FFFFFF",
            },
            "text": {"primary": "#111111", "secondary": "#333333"},
        },
        "typography": {"family": "sans", "scale": "base", "weights": ["400", "600"]},
        "radius": "medium",
        "shadow": "soft",
        "spacing": "medium",
        "layout_patterns": [],
    }


def test_style_reference_image_limit():
    images = [StyleImage(source="url", url=f"https://example.com/{i}.png") for i in range(4)]
    with pytest.raises(ValidationError):
        StyleReference(images=images)


def test_apply_scope_specific_pages():
    service = StyleReferenceService()
    tokens = _sample_tokens()
    scope = StyleScope(type="specific_pages", pages=["index", "pricing"])
    result = service.apply_scope(tokens, scope, target_pages=["index"])
    assert result["index"] == tokens
    assert result["pricing"] == tokens
    assert "*" not in result


def test_normalize_profile_tokens():
    profile_tokens = {
        "colors": {
            "primary": "#111111",
            "accent": "#222222",
            "bg": "#ffffff",
            "surface": "#f0f0f0",
            "muted": "#999999",
        },
        "typography": {
            "heading": {"family": "Sora"},
            "body": {"family": "DM Sans"},
            "scale": "modern",
        },
        "radius": "medium",
        "shadow": "soft",
        "spacing": "relaxed",
    }
    normalized = normalize_style_tokens(profile_tokens)
    assert "background" in normalized["colors"]
    assert normalized["spacing"] == "airy"


def test_tokens_to_global_style_mapping():
    tokens = _sample_tokens()
    tokens["radius"] = "pill"
    tokens["spacing"] = "tight"
    tokens["typography"]["scale"] = "large"
    global_style = tokens_to_global_style(tokens)
    assert global_style["border_radius"] == "999px"
    assert global_style["spacing_unit"] == "6px"
    assert global_style["font_size_heading"] == "28px"
