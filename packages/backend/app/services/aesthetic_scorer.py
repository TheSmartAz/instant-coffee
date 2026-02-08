from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterable, List, Optional

from pydantic import ValidationError

from ..config import Settings, get_settings
from ..llm.model_pool import ModelRole
from ..schemas.aesthetic import (
    AestheticDimension,
    AestheticDimensionScores,
    AestheticScore,
    AestheticSeverity,
    AestheticSuggestion,
    apply_threshold,
)
from ..agents.base import BaseAgent

logger = logging.getLogger(__name__)

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)

_DIMENSION_ALIASES = {
    "visualHierarchy": "visualHierarchy",
    "visual_hierarchy": "visualHierarchy",
    "hierarchy": "visualHierarchy",
    "colorHarmony": "colorHarmony",
    "color_harmony": "colorHarmony",
    "color": "colorHarmony",
    "spacingConsistency": "spacingConsistency",
    "spacing_consistency": "spacingConsistency",
    "spacing": "spacingConsistency",
    "alignment": "alignment",
    "align": "alignment",
    "readability": "readability",
    "readable": "readability",
    "mobileAdaptation": "mobileAdaptation",
    "mobile_adaptation": "mobileAdaptation",
    "mobile": "mobileAdaptation",
}

_SPACING_KEYS = {
    "gap",
    "rowGap",
    "columnGap",
    "padding",
    "paddingTop",
    "paddingBottom",
    "paddingLeft",
    "paddingRight",
    "paddingX",
    "paddingY",
    "margin",
    "marginTop",
    "marginBottom",
    "marginLeft",
    "marginRight",
    "marginX",
    "marginY",
}


class AestheticScorerAgent(BaseAgent):
    """LLM-based aesthetic scoring agent."""

    agent_type = "aesthetic_scorer"

    SCORING_PROMPT = """
    Analyze the visual design quality of this page on a 0-100 scale for each dimension:

    1. **Visual Hierarchy**: Clear information hierarchy? Strong title/body/supporting text contrast?
    2. **Color Harmony**: Primary/secondary/accent colors feel cohesive?
    3. **Spacing Consistency**: Spacing follows a consistent rhythm (8px grid)?
    4. **Alignment**: Elements align consistently without random offsets?
    5. **Readability**: Font sizes/line heights/contrast are readable?
    6. **Mobile Adaptation**: Touch targets are large enough; scrolling feels smooth?

    For any dimension below 70, provide specific improvement suggestions.

    Return JSON only:
    {
      "overall": 75,
      "dimensions": {
        "visualHierarchy": 80,
        "colorHarmony": 70,
        "spacingConsistency": 75,
        "alignment": 85,
        "readability": 72,
        "mobileAdaptation": 68
      },
      "suggestions": [
        {
          "dimension": "mobileAdaptation",
          "severity": "warning",
          "message": "Primary button height is under 44px; increase to 48px",
          "location": "button-primary",
          "autoFixable": true
        }
      ]
    }
    """

    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        session_id: Optional[str] = None,
        db: Any = None,
        event_emitter: Any = None,
        agent_id: Optional[str] = None,
    ) -> None:
        resolved_settings = settings or get_settings()
        super().__init__(
            db,
            session_id or "",
            resolved_settings,
            event_emitter=event_emitter,
            agent_id=agent_id,
            emit_lifecycle_events=bool(event_emitter),
            model_role=ModelRole.VALIDATOR,
        )

    async def score(
        self,
        page_schema: dict,
        rendered_html: Optional[str],
        style_tokens: Optional[dict],
        *,
        product_type: Optional[str] = None,
    ) -> AestheticScore:
        payload = self._build_prompt_payload(page_schema, rendered_html, style_tokens)
        if not self._has_api_key():
            return self._fallback_score(page_schema, style_tokens, product_type=product_type)

        try:
            response = await self._call_llm(
                messages=[
                    {"role": "system", "content": self.SCORING_PROMPT},
                    {"role": "user", "content": payload},
                ],
                agent_type=self.agent_type,
                temperature=self.settings.temperature,
                stream=False,
                context="aesthetic-scoring",
                model_role=ModelRole.VALIDATOR,
                product_type=product_type,
            )
            parsed = self._parse_score(getattr(response, "content", "") or "")
            score = self._build_score(parsed, product_type=product_type)
            if score is not None:
                return score
        except Exception:
            logger.exception("Aesthetic scoring failed; falling back to defaults")

        return self._fallback_score(page_schema, style_tokens, product_type=product_type)

    def _has_api_key(self) -> bool:
        return bool(
            getattr(self.settings, "default_key", None)
            or getattr(self.settings, "openai_api_key", None)
        )

    def _build_prompt_payload(
        self,
        page_schema: dict,
        rendered_html: Optional[str],
        style_tokens: Optional[dict],
    ) -> str:
        schema_payload = json.dumps(page_schema or {}, ensure_ascii=False, indent=2)
        tokens_payload = json.dumps(style_tokens or {}, ensure_ascii=False, indent=2)
        if rendered_html:
            return (
                f"Page schema:\n{schema_payload}\n\n"
                f"Style tokens:\n{tokens_payload}\n\n"
                f"Rendered HTML:\n{rendered_html}"
            )
        return f"Page schema:\n{schema_payload}\n\nStyle tokens:\n{tokens_payload}"

    def _parse_score(self, response: str) -> Optional[dict]:
        text = (response or "").strip()
        if not text:
            return None
        match = _JSON_BLOCK.search(text)
        if match:
            text = match.group(1)
        else:
            brace_match = re.search(r"\{[\s\S]*\}", text)
            if brace_match:
                text = brace_match.group(0)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _build_score(self, payload: Optional[dict], *, product_type: Optional[str]) -> Optional[AestheticScore]:
        if not isinstance(payload, dict):
            return None
        normalized = self._normalize_payload(payload)
        try:
            score = AestheticScore.model_validate(normalized)
        except ValidationError:
            return None
        return apply_threshold(score, product_type, getattr(self.settings, "aesthetic_thresholds", None))

    def _normalize_payload(self, payload: dict) -> dict:
        dimensions = self._normalize_dimensions(payload.get("dimensions"))
        overall = self._to_int(payload.get("overall"))
        suggestions = self._normalize_suggestions(payload.get("suggestions"), dimensions)
        return {
            "overall": overall,
            "dimensions": dimensions,
            "suggestions": suggestions,
            "passThreshold": bool(payload.get("passThreshold", False)),
        }

    def _normalize_dimensions(self, value: Any) -> dict:
        base = {}
        if isinstance(value, dict):
            for key, raw in value.items():
                normalized = self._normalize_dimension_key(key)
                if not normalized:
                    continue
                base[normalized] = self._to_int(raw)
        fallback = self._to_int(base.get("visualHierarchy"))
        if fallback is None:
            fallback = 70
        for key in AestheticDimensionScores.model_fields:
            if key not in base or base[key] is None:
                base[key] = fallback
        return base

    def _normalize_suggestions(self, value: Any, dimensions: dict) -> List[dict]:
        suggestions: List[dict] = []
        if isinstance(value, list):
            for raw in value:
                normalized = self._normalize_suggestion(raw)
                if normalized:
                    suggestions.append(normalized)
        if not suggestions:
            suggestions = self._suggestions_from_dimensions(dimensions)
        return suggestions

    def _normalize_suggestion(self, raw: Any) -> Optional[dict]:
        if not isinstance(raw, dict):
            return None
        dimension = self._normalize_dimension_key(raw.get("dimension"))
        if not dimension:
            return None
        severity = self._normalize_severity(raw.get("severity"))
        message = str(raw.get("message") or "").strip()
        if not message:
            return None
        return {
            "dimension": dimension,
            "severity": severity,
            "message": message,
            "location": raw.get("location"),
            "autoFixable": bool(raw.get("autoFixable", False)),
        }

    def _suggestions_from_dimensions(self, dimensions: dict) -> List[dict]:
        suggestions: List[dict] = []
        for key, score in dimensions.items():
            value = self._to_int(score)
            if value is None or value >= 70:
                continue
            severity = "critical" if value < 60 else "warning"
            auto_fixable = key in {
                AestheticDimension.MOBILE_ADAPTATION.value,
                AestheticDimension.SPACING_CONSISTENCY.value,
            }
            suggestions.append(
                {
                    "dimension": key,
                    "severity": severity,
                    "message": f"{key} is below target; consider improving visual details.",
                    "location": None,
                    "autoFixable": auto_fixable,
                }
            )
        return suggestions

    def _normalize_dimension_key(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        key = str(value).strip()
        if not key:
            return None
        normalized = _DIMENSION_ALIASES.get(key)
        if normalized:
            return normalized
        lowered = key.replace(" ", "_").replace("-", "_").lower()
        return _DIMENSION_ALIASES.get(lowered)

    def _normalize_severity(self, value: Any) -> str:
        if value is None:
            return AestheticSeverity.INFO.value
        normalized = str(value).strip().lower()
        if normalized in {"info", "warning", "critical"}:
            return normalized
        if normalized in {"warn", "medium"}:
            return AestheticSeverity.WARNING.value
        if normalized in {"high", "severe"}:
            return AestheticSeverity.CRITICAL.value
        return AestheticSeverity.INFO.value

    def _to_int(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return None

    def _fallback_score(
        self,
        page_schema: dict,
        style_tokens: Optional[dict],
        *,
        product_type: Optional[str],
    ) -> AestheticScore:
        base = 68
        if not style_tokens:
            base = 62
        components = page_schema.get("components") if isinstance(page_schema, dict) else None
        if not isinstance(components, list) or not components:
            base = min(base, 58)
        dimensions = AestheticDimensionScores(
            visualHierarchy=base,
            colorHarmony=base,
            spacingConsistency=base,
            alignment=base,
            readability=base,
            mobileAdaptation=base,
        )
        score = AestheticScore(overall=None, dimensions=dimensions, suggestions=[])
        score = apply_threshold(score, product_type, getattr(self.settings, "aesthetic_thresholds", None))
        if not score.suggestions:
            score.suggestions = [
                AestheticSuggestion(
                    dimension=AestheticDimension.SPACING_CONSISTENCY,
                    severity=AestheticSeverity.INFO,
                    message="Check that spacing follows a consistent 8px grid.",
                    autoFixable=True,
                ),
                AestheticSuggestion(
                    dimension=AestheticDimension.MOBILE_ADAPTATION,
                    severity=AestheticSeverity.INFO,
                    message="Ensure touch targets meet the 44px minimum size.",
                    autoFixable=True,
                ),
            ]
        return score


def auto_fix_suggestions(
    page_schema: dict,
    suggestions: Iterable[AestheticSuggestion | dict],
    *,
    dry_run: bool = False,
) -> dict:
    """Apply auto-fixable suggestions to a page schema."""
    if not isinstance(page_schema, dict):
        return page_schema
    try:
        working = json.loads(json.dumps(page_schema, ensure_ascii=False))
    except (TypeError, ValueError):
        working = dict(page_schema)

    normalized_suggestions = _normalize_suggestions(suggestions)
    if dry_run:
        return working

    for suggestion in normalized_suggestions:
        if not suggestion.autoFixable:
            continue
        if suggestion.dimension == AestheticDimension.MOBILE_ADAPTATION:
            fix_touch_targets(working, suggestion)
        elif suggestion.dimension == AestheticDimension.SPACING_CONSISTENCY:
            fix_spacing(working, suggestion)

    return working


def fix_touch_targets(page_schema: dict, suggestion: AestheticSuggestion | None = None) -> None:
    for component in _walk_components(page_schema):
        comp_id = str(component.get("id") or "").lower()
        if not comp_id:
            continue
        if "button" not in comp_id and "cta" not in comp_id:
            continue
        props = component.get("props")
        if not isinstance(props, dict):
            continue
        _ensure_prop(props, "size", "lg")
        _append_class(props, "className", "min-h-[48px] py-3")
        _ensure_style_min_height(props, 48)


def fix_spacing(page_schema: dict, suggestion: AestheticSuggestion | None = None) -> None:
    for component in _walk_components(page_schema):
        props = component.get("props")
        if not isinstance(props, dict):
            continue
        for key in list(props.keys()):
            if key not in _SPACING_KEYS:
                continue
            _adjust_prop_spacing(props, key)
        _adjust_style_spacing(props)


def _walk_components(schema: dict) -> Iterable[dict]:
    components = schema.get("components")
    if not isinstance(components, list):
        return []
    stack: List[dict] = []
    for comp in components:
        if isinstance(comp, dict):
            stack.append(comp)
    seen: List[dict] = []
    while stack:
        comp = stack.pop(0)
        seen.append(comp)
        children = comp.get("children")
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    stack.append(child)
    return seen


def _normalize_suggestions(
    suggestions: Iterable[AestheticSuggestion | dict],
) -> List[AestheticSuggestion]:
    normalized: List[AestheticSuggestion] = []
    for suggestion in suggestions or []:
        if isinstance(suggestion, AestheticSuggestion):
            normalized.append(suggestion)
            continue
        if isinstance(suggestion, dict):
            try:
                normalized.append(AestheticSuggestion.model_validate(suggestion))
            except ValidationError:
                continue
    return normalized


def _ensure_prop(props: dict, key: str, value: Any) -> None:
    existing = props.get(key)
    if isinstance(existing, dict) and existing.get("type") == "static":
        existing_value = existing.get("value")
        if existing_value == value:
            return
        existing["value"] = value
        return
    props[key] = {"type": "static", "value": value}


def _append_class(props: dict, key: str, value: str) -> None:
    existing = props.get(key)
    if isinstance(existing, dict) and existing.get("type") == "static":
        existing_value = str(existing.get("value") or "")
        if value in existing_value:
            return
        combined = (existing_value + " " + value).strip()
        existing["value"] = combined
        return
    props[key] = {"type": "static", "value": value}


def _ensure_style_min_height(props: dict, min_height: int) -> None:
    style = props.get("style")
    if isinstance(style, dict) and style.get("type") == "static" and isinstance(style.get("value"), dict):
        style_value = dict(style.get("value"))
    else:
        style_value = {}
    existing = style_value.get("minHeight")
    resolved = _coerce_number(existing)
    if resolved is None or resolved < min_height:
        style_value["minHeight"] = f"{min_height}px"
    props["style"] = {"type": "static", "value": style_value}


def _adjust_prop_spacing(props: dict, key: str) -> None:
    value = props.get(key)
    if isinstance(value, dict) and value.get("type") == "static":
        new_value = _snap_spacing(value.get("value"))
        if new_value is not None:
            value["value"] = new_value
        return
    new_value = _snap_spacing(value)
    if new_value is not None:
        props[key] = {"type": "static", "value": new_value}


def _adjust_style_spacing(props: dict) -> None:
    style = props.get("style")
    if not isinstance(style, dict) or style.get("type") != "static":
        return
    style_value = style.get("value")
    if not isinstance(style_value, dict):
        return
    updated = False
    for key in list(style_value.keys()):
        if key not in _SPACING_KEYS:
            continue
        snapped = _snap_spacing(style_value.get(key))
        if snapped is not None and snapped != style_value.get(key):
            style_value[key] = snapped
            updated = True
    if updated:
        style["value"] = style_value
        props["style"] = style


def _snap_spacing(value: Any, *, base: int = 8) -> Optional[Any]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(round(float(value) / base) * base)
    if isinstance(value, str):
        raw = value.strip()
        if raw.endswith("px"):
            number = _coerce_number(raw[:-2])
            if number is None:
                return None
            snapped = int(round(float(number) / base) * base)
            return f"{snapped}px"
    return None


def _coerce_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


__all__ = [
    "AestheticScorerAgent",
    "auto_fix_suggestions",
    "fix_touch_targets",
    "fix_spacing",
]
