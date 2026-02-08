from __future__ import annotations

import json
from typing import Dict

from ..schemas.scenario import (
    DataModel,
    EcommerceModel,
    KanbanModel,
    LandingModel,
    ManualModel,
    TravelModel,
)


def _format_model(model: DataModel) -> str:
    return json.dumps(model.model_dump(by_alias=True, exclude_none=True), ensure_ascii=True, indent=2)


def _build_prompt(scene: str, model: DataModel, example: dict | None = None) -> str:
    prompt = (
        "You are generating structured JSON for a scene-specific product document.\n\n"
        f"Scene: {scene}\n"
        "Return JSON only. The output must include:\n"
        "- product_type (must equal the scene)\n"
        "- complexity (simple|medium|complex)\n"
        "- pages (slug, role, title)\n"
        "- data_model (entities and relations as defined below)\n\n"
        "Data model reference:\n"
        f"{_format_model(model)}\n\n"
        "Rules:\n"
        "- Use the same entity names, fields, and relations as the reference.\n"
        "- Keep field names and types unchanged.\n"
        "- Primary keys must match the reference.\n"
    )
    if example:
        prompt += "\nExample:\n" + json.dumps(example, ensure_ascii=True, indent=2) + "\n"
    return prompt


_ECOMMERCE_EXAMPLE = {
    "product_type": "ecommerce",
    "complexity": "medium",
    "pages": [
        {"slug": "index", "role": "catalog", "title": "Home"},
        {"slug": "product", "role": "detail", "title": "Product Detail"},
        {"slug": "checkout", "role": "checkout", "title": "Checkout"},
    ],
    "data_model": EcommerceModel().model_dump(by_alias=True, exclude_none=True),
}

_TRAVEL_EXAMPLE = {
    "product_type": "travel",
    "complexity": "medium",
    "pages": [
        {"slug": "index", "role": "overview", "title": "Trip Overview"},
        {"slug": "day-plan", "role": "plan", "title": "Day Plan"},
        {"slug": "detail", "role": "detail", "title": "Location Detail"},
    ],
    "data_model": TravelModel().model_dump(by_alias=True, exclude_none=True),
}


SCENE_PROMPTS: Dict[str, str] = {
    "ecommerce": _build_prompt("ecommerce", EcommerceModel(), _ECOMMERCE_EXAMPLE),
    "travel": _build_prompt("travel", TravelModel(), _TRAVEL_EXAMPLE),
    "manual": _build_prompt("manual", ManualModel()),
    "kanban": _build_prompt("kanban", KanbanModel()),
    "landing": _build_prompt("landing", LandingModel()),
}


def get_scene_prompt(scene: str) -> str:
    return SCENE_PROMPTS.get((scene or "").strip().lower(), "")


__all__ = ["SCENE_PROMPTS", "get_scene_prompt"]
