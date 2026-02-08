import asyncio
import pytest

from app.agents.orchestrator import AgentOrchestrator
from app.db.models import Session
from app.schemas.style_reference import StyleImage, StyleReference, StyleScope, StyleTokens
from app.services.style_reference import StyleReferenceService


class TestStyleReferenceE2E:
    def test_style_reference_validation_limits_images(self):
        images = [
            StyleImage(source="url", url="https://example.com/1.png"),
            StyleImage(source="url", url="https://example.com/2.png"),
            StyleImage(source="url", url="https://example.com/3.png"),
        ]
        ref = StyleReference(mode="full_mimic", images=images)
        assert len(ref.images) == 3

        too_many = images + [StyleImage(source="url", url="https://example.com/4.png")]
        with pytest.raises(ValueError):
            StyleReference(mode="full_mimic", images=too_many)

    def test_style_reference_mode_validation(self):
        ref = StyleReference(mode="style_only", images=[])
        assert ref.mode == "style_only"
        with pytest.raises(ValueError):
            StyleReference(mode="invalid", images=[])

    def test_style_token_extraction_full_mimic(self, test_settings):
        service = StyleReferenceService(settings=test_settings)
        tokens = StyleTokens(
            colors={"primary": "#111111", "accent": "#2F6BFF"},
            typography={"family": "Test", "scale": "large"},
            radius="medium",
            shadow="soft",
            spacing="airy",
            layout_patterns=["hero-left", "card-grid"],
        )

        async def _fake_extract(images, mode, **kwargs):
            return tokens

        async def _fake_check(**kwargs):
            return True

        service.check_vision_capability = _fake_check
        service._extract_with_mode = _fake_extract

        images = [StyleImage(source="url", url="https://example.com/style.png")]
        extracted = asyncio.run(service.extract_style(images, mode="full_mimic"))

        assert extracted is not None
        assert extracted.layout_patterns

    def test_scope_filtering_applies_tokens_to_pages(self, test_settings):
        service = StyleReferenceService(settings=test_settings)
        tokens = {
            "colors": {"primary": "#111111"},
            "typography": {"family": "Test"},
            "radius": "medium",
            "shadow": "soft",
            "spacing": "airy",
            "layout_patterns": ["hero"],
        }
        scope = StyleScope(type="specific_pages", pages=["home", "about"])
        mapping = service.apply_scope(tokens, scope, target_pages=["home", "about", "pricing"])

        assert set(mapping.keys()) == {"home", "about"}

    def test_fallback_to_profile_tokens_when_no_images(self, test_db, test_settings):
        session = Session(id="e2e-style-profile", title="Profile")
        test_db.add(session)
        test_db.commit()

        orchestrator = AgentOrchestrator(test_db, session)
        context = asyncio.run(
            orchestrator._resolve_style_context(
                style_reference=None,
                user_message="Create a landing page",
                target_pages=None,
                product_doc=None,
            )
        )

        assert context is not None
        assert context.get("tokens")
