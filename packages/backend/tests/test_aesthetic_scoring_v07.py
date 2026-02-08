from __future__ import annotations

import asyncio

from app.config import Settings
from app.graph.nodes.aesthetic_scorer import aesthetic_scorer_node
from app.schemas.aesthetic import (
    AestheticDimension,
    AestheticDimensionScores,
    AestheticScore,
    AestheticSeverity,
    AestheticSuggestion,
    apply_threshold,
)
from app.services.aesthetic_scorer import AestheticScorerAgent, auto_fix_suggestions


def test_threshold_evaluation() -> None:
    dims = AestheticDimensionScores(
        visualHierarchy=69,
        colorHarmony=69,
        spacingConsistency=69,
        alignment=69,
        readability=69,
        mobileAdaptation=69,
    )
    score = AestheticScore(overall=69, dimensions=dims, suggestions=[])
    landing = apply_threshold(score, "landing")
    assert landing.passThreshold is False
    card = apply_threshold(score, "card")
    assert card.passThreshold is True


def test_parse_score_from_json_block() -> None:
    settings = Settings(default_key="test-key", openai_base_url="http://localhost")
    agent = AestheticScorerAgent(settings=settings)
    response = """
    ```json
    {"overall": 80, "dimensions": {"visual_hierarchy": 82, "colorHarmony": 75, "spacingConsistency": 70, "alignment": 80, "readability": 78, "mobileAdaptation": 65},
     "suggestions": [{"dimension": "mobileAdaptation", "severity": "warning", "message": "Increase button size", "autoFixable": true}]}
    ```
    """
    parsed = agent._parse_score(response)
    assert isinstance(parsed, dict)
    normalized = agent._normalize_payload(parsed)
    assert normalized["dimensions"]["visualHierarchy"] == 82
    assert normalized["suggestions"][0]["autoFixable"] is True


def test_auto_fix_touch_targets() -> None:
    schema = {
        "components": [
            {
                "id": "button-primary",
                "key": "cta-1",
                "props": {
                    "label": {"type": "static", "value": "Buy now"},
                    "size": {"type": "static", "value": "sm"},
                },
            }
        ]
    }
    suggestion = AestheticSuggestion(
        dimension=AestheticDimension.MOBILE_ADAPTATION,
        severity=AestheticSeverity.WARNING,
        message="Increase touch target",
        autoFixable=True,
    )
    fixed = auto_fix_suggestions(schema, [suggestion])
    props = fixed["components"][0]["props"]
    assert props["size"]["value"] == "lg"
    assert "min-h-[48px]" in props["className"]["value"]


def test_auto_fix_spacing() -> None:
    schema = {
        "components": [
            {
                "id": "section-header",
                "key": "header-1",
                "props": {
                    "gap": {"type": "static", "value": 10},
                    "style": {"type": "static", "value": {"padding": "10px"}},
                },
            }
        ]
    }
    suggestion = AestheticSuggestion(
        dimension=AestheticDimension.SPACING_CONSISTENCY,
        severity=AestheticSeverity.INFO,
        message="Use 8px grid",
        autoFixable=True,
    )
    fixed = auto_fix_suggestions(schema, [suggestion])
    props = fixed["components"][0]["props"]
    assert props["gap"]["value"] == 8
    assert props["style"]["value"]["padding"] == "8px"


def test_aesthetic_scorer_node_fallback(monkeypatch) -> None:
    monkeypatch.setattr(AestheticScorerAgent, "_has_api_key", lambda self: False)
    state = {
        "session_id": "session-1",
        "page_schemas": [
            {
                "slug": "index",
                "title": "Landing",
                "layout": "default",
                "components": [
                    {
                        "id": "button-primary",
                        "key": "cta-1",
                        "props": {"label": {"type": "static", "value": "Start"}},
                    }
                ],
            }
        ],
        "style_tokens": {},
        "product_doc": {"product_type": "landing"},
    }

    result = asyncio.run(aesthetic_scorer_node(state))
    assert isinstance(result.get("aesthetic_scores"), dict)
    assert "dimensions" in result["aesthetic_scores"]
    assert result["aesthetic_scores"].get("passThreshold") is not None
