from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ...services.product_doc import ProductDocService


@dataclass
class DocTierDecision:
    doc_tier: str
    reasoning: str


class DocTierSelector:
    def select(self, product_type: Optional[str], complexity: Optional[str], override: Optional[str] = None) -> DocTierDecision:
        doc_tier = ProductDocService.select_doc_tier(product_type, complexity, override)
        reasoning = "Mapped complexity to doc tier."
        if product_type and product_type.lower().strip() in {"landing", "card", "invitation"}:
            reasoning = "Static product type forces checklist tier."
        if override:
            reasoning = "Doc tier override applied."
        return DocTierDecision(doc_tier=doc_tier, reasoning=reasoning)


__all__ = ["DocTierSelector", "DocTierDecision"]
