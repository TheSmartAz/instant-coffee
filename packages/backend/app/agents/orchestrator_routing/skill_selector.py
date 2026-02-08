from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ...services.product_doc import ProductDocService
from ...services.skills import SkillManifest, SkillsRegistry


@dataclass
class SkillSelection:
    skill_id: Optional[str]
    reasoning: str
    manifest: Optional[SkillManifest] = None


class SkillSelector:
    def __init__(self, registry: SkillsRegistry | None = None, *, default_skill_id: str = "static-landing-v1") -> None:
        self.registry = registry or SkillsRegistry()
        self.default_skill_id = default_skill_id

    def select(self, product_type: str, complexity: Optional[str] = None) -> SkillSelection:
        normalized = (product_type or "").lower().strip()
        if not normalized or normalized == "unknown":
            fallback = self._fallback_skill("unknown product type")
            return fallback

        normalized_complexity = ProductDocService.normalize_complexity(complexity) if complexity else None
        matches = self.registry.find_skills(normalized, normalized_complexity)
        if not matches and normalized_complexity:
            doc_tier = ProductDocService.normalize_doc_tier(normalized_complexity)
            if doc_tier and doc_tier != normalized_complexity:
                matches = self.registry.find_skills(normalized, doc_tier)
        if matches:
            manifest = matches[0]
            return SkillSelection(
                skill_id=manifest.id,
                reasoning=f"Selected highest priority skill for {normalized}.",
                manifest=manifest,
            )

        fallback = self._fallback_skill(f"no skill match for {normalized}")
        return fallback

    def _fallback_skill(self, reason: str) -> SkillSelection:
        manifest = self.registry.get(self.default_skill_id)
        if manifest:
            return SkillSelection(
                skill_id=manifest.id,
                reasoning=f"Fallback to {manifest.id}: {reason}.",
                manifest=manifest,
            )
        all_skills = self.registry.list()
        if all_skills:
            first = all_skills[0]
            return SkillSelection(
                skill_id=first.id,
                reasoning=f"Fallback to {first.id}: {reason}.",
                manifest=first,
            )
        return SkillSelection(skill_id=None, reasoning="No skills available.")


__all__ = ["SkillSelector", "SkillSelection"]
