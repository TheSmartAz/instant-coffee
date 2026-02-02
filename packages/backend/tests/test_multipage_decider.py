import pytest

from app.agents.multipage_decider import AutoMultiPageDecider, calculate_confidence
from app.events.emitter import EventEmitter


class DummyDoc:
    def __init__(self, structured: dict) -> None:
        self.structured = structured


def test_calculate_confidence_high() -> None:
    structured = {
        "pages": [
            {"sections": ["hero", "features", "cta"]},
            {"sections": ["pricing", "faq", "cta"]},
            {"sections": ["about", "team", "values", "contact"]},
        ],
        "features": [
            {"priority": "must"},
            {"priority": "must"},
            {"priority": "must"},
            {"priority": "must"},
        ],
        "description": "Includes about and contact pages",
    }
    score, reasons = calculate_confidence(structured)
    assert score == pytest.approx(1.0)
    assert reasons


def test_decide_suggest_multi_page() -> None:
    structured = {
        "pages": [
            {"title": "Home", "slug": "index", "sections": ["hero"]},
            {"title": "About", "slug": "about", "sections": ["story"]},
        ],
        "features": [
            {"priority": "must"},
            {"priority": "must"},
        ],
        "description": "About page details",
    }
    decider = AutoMultiPageDecider()
    result = decider.decide(DummyDoc(structured))
    assert result.decision == "suggest_multi_page"
    assert result.suggested_pages


def test_decide_single_page() -> None:
    structured = {
        "pages": [{"title": "Home", "slug": "index", "sections": ["hero", "cta"]}],
        "features": [{"priority": "nice"}],
        "description": "Simple landing page",
    }
    decider = AutoMultiPageDecider()
    result = decider.decide(DummyDoc(structured))
    assert result.decision == "single_page"
    assert any("single page" in reason.lower() for reason in result.reasons)


def test_decision_emits_event() -> None:
    emitter = EventEmitter()
    structured = {
        "pages": [
            {"title": "Home", "slug": "index", "sections": ["hero"]},
            {"title": "About", "slug": "about", "sections": ["story"]},
            {"title": "Contact", "slug": "contact", "sections": ["form"]},
        ],
        "features": [{"priority": "must"}, {"priority": "must"}, {"priority": "must"}],
        "description": "About and contact info",
    }
    decider = AutoMultiPageDecider(event_emitter=emitter)
    decider.decide(DummyDoc(structured))
    events = emitter.get_events()
    assert events
    assert events[-1].type.value == "multipage_decision_made"
