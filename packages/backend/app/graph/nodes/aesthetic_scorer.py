from __future__ import annotations

from typing import Any, Optional

from ...config import get_settings
from ...db.utils import get_db
from ...events.models import AestheticScoreEvent
from ...services.page import PageService
from ...services.aesthetic_scorer import AestheticScorerAgent, auto_fix_suggestions


def _as_dict(state: Any) -> dict:
    if isinstance(state, dict):
        return dict(state)
    if hasattr(state, "__dict__"):
        return dict(state.__dict__)
    return {}


def _resolve_product_type(state: dict) -> Optional[str]:
    product_doc = state.get("product_doc")
    if isinstance(product_doc, dict):
        value = product_doc.get("product_type") or product_doc.get("productType")
        if value:
            return str(value).strip().lower()
    return None



def _emit_score_event(session_id: str | None, slug: str | None, score: dict, event_emitter: Any | None) -> None:
    if not session_id or event_emitter is None:
        return
    resolved_slug = str(slug or "").strip().lower()
    if not resolved_slug:
        return
    try:
        with get_db() as db:
            page = PageService(db).get_by_slug(session_id, resolved_slug)
            if page is None:
                return
            event_emitter.emit(
                AestheticScoreEvent(
                    session_id=session_id,
                    page_id=page.id,
                    slug=page.slug,
                    score=score,
                )
            )
    except Exception:
        return

def _select_primary_schema(page_schemas: list[dict]) -> Optional[dict]:
    if not page_schemas:
        return None
    for schema in page_schemas:
        if not isinstance(schema, dict):
            continue
        slug = str(schema.get("slug") or "").lower()
        if slug in {"", "index", "home", "landing"}:
            return schema
        role = str(schema.get("role") or schema.get("page_role") or "").lower()
        if role in {"primary", "home", "landing"}:
            return schema
    return page_schemas[0] if isinstance(page_schemas[0], dict) else None


async def aesthetic_scorer_node(state: Any, *, event_emitter: Any | None = None) -> dict:
    updated = _as_dict(state)
    updated.setdefault("aesthetic_scores", None)
    updated.setdefault("aesthetic_suggestions", [])

    page_schemas = updated.get("page_schemas")
    if not isinstance(page_schemas, list) or not page_schemas:
        return updated

    style_tokens = updated.get("style_tokens")
    if not isinstance(style_tokens, dict):
        style_tokens = {}

    scorer = AestheticScorerAgent(
        settings=get_settings(),
        session_id=updated.get("session_id"),
        event_emitter=event_emitter,
    )
    product_type = _resolve_product_type(updated)
    primary_schema = _select_primary_schema(page_schemas)

    if primary_schema is None:
        return updated

    score = await scorer.score(primary_schema, None, style_tokens, product_type=product_type)
    score_payload = score.model_dump(mode="json")
    updated["aesthetic_scores"] = score_payload
    updated["aesthetic_suggestions"] = [
        suggestion.model_dump(mode="json") for suggestion in score.suggestions
    ]
    _emit_score_event(updated.get("session_id"), primary_schema.get("slug"), score_payload, event_emitter)

    if score.suggestions:
        fixed_schemas = []
        for schema in page_schemas:
            if isinstance(schema, dict):
                fixed_schemas.append(auto_fix_suggestions(schema, score.suggestions))
            else:
                fixed_schemas.append(schema)
        updated["page_schemas"] = fixed_schemas

    return updated


__all__ = ["aesthetic_scorer_node"]
