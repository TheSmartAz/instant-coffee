from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AestheticSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AestheticDimension(str, Enum):
    VISUAL_HIERARCHY = "visualHierarchy"
    COLOR_HARMONY = "colorHarmony"
    SPACING_CONSISTENCY = "spacingConsistency"
    ALIGNMENT = "alignment"
    READABILITY = "readability"
    MOBILE_ADAPTATION = "mobileAdaptation"


DIMENSION_WEIGHTS: Dict[str, float] = {
    AestheticDimension.VISUAL_HIERARCHY.value: 0.25,
    AestheticDimension.COLOR_HARMONY.value: 0.20,
    AestheticDimension.SPACING_CONSISTENCY.value: 0.20,
    AestheticDimension.ALIGNMENT.value: 0.15,
    AestheticDimension.READABILITY.value: 0.10,
    AestheticDimension.MOBILE_ADAPTATION.value: 0.10,
}

DEFAULT_AESTHETIC_THRESHOLDS: Dict[str, Dict[str, int]] = {
    "landing": {"pass": 70, "suggest": 85},
    "card": {"pass": 65, "suggest": 80},
    "default": {"pass": 60, "suggest": 75},
}


class AestheticDimensionScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visualHierarchy: int = Field(ge=0, le=100)
    colorHarmony: int = Field(ge=0, le=100)
    spacingConsistency: int = Field(ge=0, le=100)
    alignment: int = Field(ge=0, le=100)
    readability: int = Field(ge=0, le=100)
    mobileAdaptation: int = Field(ge=0, le=100)

    def weighted_overall(self) -> int:
        total = 0.0
        for key, weight in DIMENSION_WEIGHTS.items():
            value = getattr(self, key, 0)
            total += float(value) * weight
        return int(round(total))


class AestheticSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: AestheticDimension
    severity: AestheticSeverity
    message: str
    location: Optional[str] = None
    autoFixable: bool = False


class AestheticScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall: Optional[int] = Field(default=None, ge=0, le=100)
    dimensions: AestheticDimensionScores
    suggestions: List[AestheticSuggestion] = Field(default_factory=list)
    passThreshold: bool = False

    @model_validator(mode="after")
    def _ensure_overall(self) -> "AestheticScore":
        if self.overall is None and self.dimensions is not None:
            self.overall = self.dimensions.weighted_overall()
        if self.overall is None:
            self.overall = 0
        return self


def resolve_thresholds(
    product_type: Optional[str],
    overrides: Optional[Dict[str, Dict[str, int]]] = None,
) -> Tuple[int, int]:
    key = (product_type or "").strip().lower()
    merged = {**DEFAULT_AESTHETIC_THRESHOLDS}
    if isinstance(overrides, dict):
        for scenario, values in overrides.items():
            if not isinstance(values, dict):
                continue
            merged[str(scenario).strip().lower()] = {
                **merged.get(str(scenario).strip().lower(), {}),
                **{k: int(v) for k, v in values.items() if isinstance(v, (int, float)) or str(v).isdigit()},
            }
    thresholds = merged.get(key) or merged.get("default", {})
    return int(thresholds.get("pass", 60)), int(thresholds.get("suggest", 75))


def apply_threshold(
    score: AestheticScore,
    product_type: Optional[str],
    overrides: Optional[Dict[str, Dict[str, int]]] = None,
) -> AestheticScore:
    pass_threshold, _ = resolve_thresholds(product_type, overrides)
    updated = score.model_copy()
    updated.passThreshold = bool((updated.overall or 0) >= pass_threshold)
    return updated


__all__ = [
    "AestheticSeverity",
    "AestheticDimension",
    "AestheticDimensionScores",
    "AestheticSuggestion",
    "AestheticScore",
    "resolve_thresholds",
    "apply_threshold",
    "DEFAULT_AESTHETIC_THRESHOLDS",
    "DIMENSION_WEIGHTS",
]
