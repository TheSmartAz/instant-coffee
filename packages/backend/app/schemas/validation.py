from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AutoChecks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wcag_contrast: str  # "pass" or "fail"
    contrast_ratio: Optional[float] = None
    line_height: str  # "pass" or "fail"
    line_height_value: Optional[float] = None
    type_scale: str  # "pass" or "fail"
    scale_difference: Optional[str] = None


class DimensionScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    typography: int = Field(ge=1, le=5)
    contrast: int = Field(ge=1, le=5)
    layout: int = Field(ge=1, le=5)
    color: int = Field(ge=1, le=5)
    cta: int = Field(ge=1, le=5)

    def total(self) -> int:
        return int(self.typography + self.contrast + self.layout + self.color + self.cta)


class AestheticScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimensions: DimensionScores
    total: Optional[int] = None
    issues: List[str] = Field(default_factory=list)
    auto_checks: AutoChecks
    passes_threshold: bool = False

    @model_validator(mode="after")
    def _compute_total(self) -> "AestheticScore":
        total = self.dimensions.total() if self.dimensions else 0
        self.total = int(total)
        self.passes_threshold = bool(self.total >= 18)
        return self


__all__ = ["AutoChecks", "DimensionScores", "AestheticScore"]
