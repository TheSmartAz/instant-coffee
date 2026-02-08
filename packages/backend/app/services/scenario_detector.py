from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Dict, List

SCENARIO_KEYWORDS: Dict[str, List[str]] = {
    "ecommerce": ["商品", "购物车", "下单", "商城", "电商", "store", "cart", "checkout"],
    "travel": ["行程", "旅行", "日程", "景点", "trip", "itinerary", "booking"],
    "manual": ["说明书", "文档", "手册", "指南", "manual", "docs", "guide"],
    "kanban": ["看板", "任务", "项目管理", "board", "task", "kanban"],
    "landing": ["落地页", "宣传页", "首页", "landing", "hero", "cta"],
}

CONFIDENCE_THRESHOLD = 0.5


@dataclass(frozen=True)
class ScenarioDetection:
    product_type: str
    confidence: float
    matched_keywords: List[str] = field(default_factory=list)


def detect_scenario(
    user_input: str,
    *,
    min_confidence: float = CONFIDENCE_THRESHOLD,
    fallback: str = "unknown",
) -> ScenarioDetection:
    text = (user_input or "").strip().lower()
    if not text:
        return ScenarioDetection(product_type=fallback, confidence=0.0, matched_keywords=[])

    scores: Dict[str, float] = {}
    matches: Dict[str, List[str]] = {}
    for scenario, keywords in SCENARIO_KEYWORDS.items():
        matched = [keyword for keyword in keywords if _keyword_match(text, keyword)]
        matches[scenario] = matched
        if matched:
            scores[scenario] = min(1.0, len(matched) / 3.0)
        else:
            scores[scenario] = 0.0

    best_scenario = max(scores, key=scores.get)
    best_score = scores[best_scenario]
    if best_score < min_confidence:
        return ScenarioDetection(
            product_type=fallback,
            confidence=best_score,
            matched_keywords=matches.get(best_scenario, []),
        )

    return ScenarioDetection(
        product_type=best_scenario,
        confidence=best_score,
        matched_keywords=matches.get(best_scenario, []),
    )


def _keyword_match(text: str, keyword: str) -> bool:
    if not keyword:
        return False
    if re.match(r"^[a-z0-9]+$", keyword):
        return re.search(rf"\b{re.escape(keyword)}\b", text) is not None
    return keyword.lower() in text


__all__ = ["SCENARIO_KEYWORDS", "CONFIDENCE_THRESHOLD", "ScenarioDetection", "detect_scenario"]
