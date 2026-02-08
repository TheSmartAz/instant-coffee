from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
import os
from typing import Any, Optional, Sequence

from ...db.models import Page, ProductDoc, Session as SessionModel
from ...services.product_doc import ProductDocService
from ...services.scenario_detector import detect_scenario
from ...services.skills import Guardrails, SkillsRegistry, load_style_profiles, load_style_router, route_style_profile
from ..classifier import ProductClassification, ProductClassifier
from .complexity import ComplexityEvaluator, ComplexityReport
from .doc_tier import DocTierDecision, DocTierSelector
from .skill_selector import SkillSelection, SkillSelector
from .targets import PageTargetResolver

logger = logging.getLogger(__name__)

_DEFAULT_PRODUCT_TYPE = "landing"


@dataclass
class RoutingDecision:
    product_type: str
    complexity: str
    skill_id: Optional[str]
    style_profile: Optional[str]
    guardrails: dict
    doc_tier: str
    target_pages: list[str]
    confidence: float
    reasoning: str
    model_prefs: dict[str, str] = field(default_factory=dict)
    complexity_report: Optional[ComplexityReport] = None


class OrchestratorRouter:
    def __init__(
        self,
        *,
        db,
        session_id: str,
        settings,
        registry: SkillsRegistry | None = None,
        classifier: ProductClassifier | None = None,
        complexity_evaluator: ComplexityEvaluator | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.db = db
        self.session_id = session_id
        self.settings = settings
        self.timeout_seconds = float(timeout_seconds)
        self.registry = registry or SkillsRegistry()
        self._allow_llm = self._can_use_llm()

        model_light = self._resolve_model_id("light")
        self.classifier = classifier or ProductClassifier(
            db,
            session_id,
            settings,
            model=model_light,
            timeout_seconds=timeout_seconds,
        )
        self.complexity_evaluator = complexity_evaluator or ComplexityEvaluator(
            db,
            session_id,
            settings,
            model=model_light,
            timeout_seconds=timeout_seconds,
        )
        self.target_resolver = PageTargetResolver()
        self.skill_selector = SkillSelector(self.registry)
        self.doc_tier_selector = DocTierSelector()

    async def route(
        self,
        user_input: str,
        *,
        project_pages: Sequence[Page] | None = None,
        explicit_targets: Sequence[str] | None = None,
        product_doc: ProductDoc | None = None,
        session: SessionModel | None = None,
    ) -> RoutingDecision:
        try:
            return await asyncio.wait_for(
                self._route_inner(
                    user_input,
                    project_pages=project_pages,
                    explicit_targets=explicit_targets,
                    product_doc=product_doc,
                    session=session,
                ),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning("Routing timed out, falling back to heuristics")
            return await self._route_fallback(
                user_input,
                project_pages=project_pages,
                explicit_targets=explicit_targets,
                product_doc=product_doc,
                session=session,
            )

    async def _route_inner(
        self,
        user_input: str,
        *,
        project_pages: Sequence[Page] | None,
        explicit_targets: Sequence[str] | None,
        product_doc: ProductDoc | None,
        session: SessionModel | None,
    ) -> RoutingDecision:
        targets = self._resolve_targets(user_input, project_pages, explicit_targets)
        existing_product, existing_complexity, existing_doc_tier = self._existing_routing(product_doc, session)

        classification: ProductClassification | None = None
        if existing_product and existing_product != "unknown":
            product_type = existing_product
            confidence = 1.0
            reasoning_parts = ["Used existing product type."]
        else:
            scenario = detect_scenario(user_input)
            if scenario.product_type != "unknown":
                product_type = scenario.product_type
                confidence = scenario.confidence
                matched = ", ".join(scenario.matched_keywords) if scenario.matched_keywords else "keywords"
                reasoning_parts = [
                    f"Scenario detector: matched {matched} (confidence {confidence:.2f})."
                ]
            else:
                classification = await self.classifier.classify(user_input, use_llm=self._allow_llm)
                product_type = classification.product_type
                confidence = classification.confidence
                reasoning_parts = [f"Classifier: {classification.reasoning} (confidence {confidence:.2f})."]

        complexity_report: ComplexityReport | None = None
        if existing_complexity and existing_complexity != "unknown":
            complexity = existing_complexity
            reasoning_parts.append("Used existing complexity.")
        else:
            complexity_report = await self.complexity_evaluator.evaluate(
                user_input,
                product_type,
                use_llm=self._allow_llm,
            )
            complexity = complexity_report.level
            reasoning_parts.append("Complexity heuristics/LLM applied.")

        selection = self.skill_selector.select(product_type, complexity)
        reasoning_parts.append(selection.reasoning)

        style_profile = self._select_style_profile(user_input, selection, product_doc)

        guardrails_payload = self._load_guardrails(selection)
        doc_tier_decision = self.doc_tier_selector.select(product_type, complexity, existing_doc_tier)
        reasoning_parts.append(doc_tier_decision.reasoning)

        model_prefs = self._resolve_model_prefs(selection)

        if confidence < 0.5:
            reasoning_parts.append("Low confidence; default fallback applied.")

        return RoutingDecision(
            product_type=product_type or _DEFAULT_PRODUCT_TYPE,
            complexity=complexity or "simple",
            skill_id=selection.skill_id,
            style_profile=style_profile,
            guardrails=guardrails_payload,
            doc_tier=doc_tier_decision.doc_tier,
            target_pages=targets,
            confidence=confidence,
            reasoning=" ".join(reasoning_parts),
            model_prefs=model_prefs,
            complexity_report=complexity_report,
        )

    async def _route_fallback(
        self,
        user_input: str,
        *,
        project_pages: Sequence[Page] | None,
        explicit_targets: Sequence[str] | None,
        product_doc: ProductDoc | None,
        session: SessionModel | None,
    ) -> RoutingDecision:
        targets = self._resolve_targets(user_input, project_pages, explicit_targets)
        existing_product, existing_complexity, existing_doc_tier = self._existing_routing(product_doc, session)
        product_type = existing_product or "unknown"
        if product_type == "unknown":
            scenario = detect_scenario(user_input)
            if scenario.product_type != "unknown":
                product_type = scenario.product_type
        if product_type == "unknown":
            product_type = _DEFAULT_PRODUCT_TYPE
        complexity_report = self.complexity_evaluator._heuristic_evaluate(user_input, product_type)
        complexity = existing_complexity or complexity_report.level
        selection = self.skill_selector.select(product_type, complexity)
        style_profile = self._select_style_profile(user_input, selection, product_doc)
        guardrails_payload = self._load_guardrails(selection)
        doc_tier_decision = self.doc_tier_selector.select(product_type, complexity, existing_doc_tier)
        model_prefs = self._resolve_model_prefs(selection)
        return RoutingDecision(
            product_type=product_type,
            complexity=complexity,
            skill_id=selection.skill_id,
            style_profile=style_profile,
            guardrails=guardrails_payload,
            doc_tier=doc_tier_decision.doc_tier,
            target_pages=targets,
            confidence=0.4,
            reasoning="Fallback routing used.",
            model_prefs=model_prefs,
            complexity_report=complexity_report,
        )

    def _resolve_targets(
        self,
        user_input: str,
        project_pages: Sequence[Page] | None,
        explicit_targets: Sequence[str] | None,
    ) -> list[str]:
        explicit = [str(item).strip() for item in (explicit_targets or []) if str(item).strip()]
        parsed = []
        if project_pages:
            parsed = self.target_resolver.parse(user_input, project_pages)
        combined = []
        seen = set()
        for slug in explicit + parsed:
            if slug in seen:
                continue
            combined.append(slug)
            seen.add(slug)
        return combined

    def _existing_routing(
        self,
        product_doc: ProductDoc | None,
        session: SessionModel | None,
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        product_type = None
        complexity = None
        doc_tier = None
        if product_doc is not None:
            structured = getattr(product_doc, "structured", None)
            if isinstance(structured, dict):
                product_type = structured.get("product_type") or structured.get("productType")
                complexity = structured.get("complexity")
                doc_tier = structured.get("doc_tier") or structured.get("docTier")
        if session is not None:
            product_type = product_type or session.product_type
            complexity = complexity or session.complexity
            doc_tier = doc_tier or session.doc_tier

        product_type = ProductDocService.normalize_product_type(product_type) or "unknown"
        complexity = ProductDocService.normalize_complexity(complexity) or "unknown"
        doc_tier = ProductDocService.normalize_doc_tier(doc_tier) if doc_tier else None
        return product_type, complexity, doc_tier

    def _select_style_profile(
        self,
        user_input: str,
        selection: SkillSelection,
        product_doc: ProductDoc | None,
    ) -> Optional[str]:
        router = load_style_router()
        router_text = self._build_style_router_text(user_input, product_doc)
        profile_id = route_style_profile(router_text, router=router)
        profiles = load_style_profiles()
        allowed = []
        if selection.manifest is not None:
            allowed = list(selection.manifest.style_profiles or [])

        if allowed:
            if profile_id not in allowed:
                default_profile = router.get("default_profile")
                if default_profile in allowed:
                    profile_id = str(default_profile)
                else:
                    profile_id = allowed[0]

        if profile_id not in profiles:
            profile_id = router.get("default_profile") or "clean-modern"
            if profile_id not in profiles and profiles:
                profile_id = next(iter(profiles.keys()))

        return str(profile_id) if profile_id else None

    def _build_style_router_text(self, user_input: str, product_doc: ProductDoc | None) -> str:
        parts = [user_input or ""]
        if product_doc is not None:
            structured = getattr(product_doc, "structured", None)
            if isinstance(structured, dict):
                design = structured.get("design_direction") or structured.get("designDirection") or {}
                if isinstance(design, dict):
                    for key in ("style", "tone", "color_preference", "colorPreference"):
                        value = design.get(key)
                        if value:
                            parts.append(str(value))
        return " ".join(part for part in parts if part)

    def _load_guardrails(self, selection: SkillSelection) -> dict:
        guardrails: Guardrails | None = None
        if selection.skill_id:
            guardrails = self.registry.get_guardrails(selection.skill_id)
        if guardrails is None:
            try:
                guardrails = self.registry.load_guardrails()
            except Exception:
                guardrails = None
        return self._guardrails_to_dict(guardrails)

    def _guardrails_to_dict(self, guardrails: Guardrails | None) -> dict:
        if guardrails is None:
            return {"hard": [], "soft": []}
        return {
            "hard": [self._rule_to_dict(rule) for rule in guardrails.hard],
            "soft": [self._rule_to_dict(rule) for rule in guardrails.soft],
        }

    def _rule_to_dict(self, rule: Any) -> dict:
        if hasattr(rule, "__dict__"):
            data = dict(rule.__dict__)
        elif isinstance(rule, dict):
            data = dict(rule)
        else:
            data = {"id": str(rule)}
        return {
            "id": data.get("id"),
            "title": data.get("title"),
            "description": data.get("description"),
            "category": data.get("category"),
            "priority": data.get("priority"),
        }

    def _resolve_model_prefs(self, selection: SkillSelection) -> dict[str, str]:
        if selection.manifest is None:
            return {}
        prefs = selection.manifest.model_prefs.to_dict()
        return {key: self._resolve_model_id(value) for key, value in prefs.items()}

    def _resolve_model_id(self, model_pref: str | None) -> str:
        if not model_pref:
            return self.settings.model
        pref = str(model_pref).strip()
        key = pref.lower()
        if key in {"light", "mid", "heavy"}:
            env_value = os.getenv(f"MODEL_{key.upper()}")
            if env_value:
                return env_value
            return self.settings.model
        return pref

    def _can_use_llm(self) -> bool:
        key = self.settings.openai_api_key or self.settings.default_key
        if not key:
            return False
        base_url = (self.settings.openai_base_url or self.settings.default_base_url or "").lower()
        if "localhost" in base_url or "127.0.0.1" in base_url:
            return False
        return True


__all__ = ["OrchestratorRouter", "RoutingDecision"]
