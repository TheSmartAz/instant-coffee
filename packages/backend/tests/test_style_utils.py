from app.utils.style import build_global_style, build_global_style_css, build_site_css, parse_color_preferences


def test_parse_color_preferences_hex() -> None:
    primary, secondary = parse_color_preferences("Use #ff00ff and #00ff00")
    assert primary == "#FF00FF"
    assert secondary == "#00FF00"


def test_parse_color_preferences_keywords() -> None:
    primary, secondary = parse_color_preferences("blue and orange")
    assert primary == "#2563EB"
    assert secondary == "#F97316"


def test_build_global_style_prefers_tone_font() -> None:
    style = build_global_style({"style": "modern", "tone": "professional"})
    assert style["font_family"].startswith("IBM Plex Sans")
    assert style["primary_color"]
    assert style["button_height"] == "44px"


def test_build_site_css_includes_globals() -> None:
    css = build_site_css({"primary_color": "#123ABC", "font_family": "Test"})
    assert "/* Site-wide Design System */" in css
    assert "--primary-color: #123ABC;" in css


def test_build_global_style_css_includes_base() -> None:
    css = build_global_style_css({"primary_color": "#123ABC", "font_family": "Test"})
    assert ":root" in css
    assert "--primary-color: #123ABC;" in css
    assert ".hide-scrollbar" in css
