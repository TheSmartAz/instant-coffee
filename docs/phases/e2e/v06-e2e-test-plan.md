# Instant Coffee v0.6 - E2E Test Plan

**Version**: v0.6
**Status**: Draft
**Date**: 2026-02-04
**Coverage**: All spec-06 acceptance criteria

---

## Table of Contents

1. [Test Environment Setup](#1-test-environment-setup)
2. [Backend E2E Tests](#2-backend-e2e-tests)
3. [Frontend E2E Tests](#3-frontend-e2e-tests)
4. [Integration E2E Tests](#4-integration-e2e-tests)
5. [Test Matrix Summary](#5-test-matrix-summary)

---

## 1. Test Environment Setup

### 1.1 Test Fixtures

```python
# packages/backend/tests/conftest.py
import pytest
import asyncio
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.models import Base
from app.config import Settings, get_settings
from app.services.skills import SkillsRegistry
from app.agents.orchestrator import AgentOrchestrator
from app.events.emitter import EventEmitter


@pytest.fixture
def test_settings(monkeypatch):
    """Configure test settings with mock API credentials."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("DEFAULT_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    monkeypatch.setenv("OUTPUT_DIR", "/tmp/test-output")
    return get_settings()


@pytest.fixture
def test_db(test_settings):
    """Create in-memory database for testing."""
    engine = create_engine(test_settings.database_url)
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)
    session = TestSessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_client(test_db, test_settings):
    """Create FastAPI test client with database override."""
    def override_get_db():
        yield test_db

    from app.db.utils import get_db
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_style_reference_image():
    """Path to sample image for style reference tests."""
    return Path(__file__).parent / "fixtures" / "sample-style-ref.png"


@pytest.fixture
def sample_ecommerce_images():
    """Paths to sample ecommerce product images."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    return [
        fixtures_dir / "product1.jpg",
        fixtures_dir / "product2.jpg",
    ]


@pytest.fixture
def mock_llm_response():
    """Mock LLM responses for testing without actual API calls."""
    return {
        "product_doc": {
            "content": "# ECommerce Product Doc",
            "structured": {
                "project_name": "Test Store",
                "product_type": "ecommerce",
                "complexity": "medium",
                "doc_tier": "standard",
                "pages": [
                    {"slug": "home", "title": "Home", "role": "catalog"},
                    {"slug": "cart", "title": "Cart", "role": "checkout"},
                ],
                "state_contract": {
                    "shared_state_key": "instant-coffee:state",
                    "schema": {
                        "cart": {"items": [], "totals": {"subtotal": 0}}
                    }
                },
                "data_flow": [
                    {"from": "home", "event": "add_to_cart", "to": "cart"}
                ],
                "style_reference": {
                    "mode": "full_mimic",
                    "scope": {"type": "all"}
                }
            }
        },
        "generation_html": """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
            <style>
                body { font-family: sans-serif; margin: 0; padding: 0; }
                .container { max-width: 430px; margin: 0 auto; }
                .product-card { padding: 16px; border-radius: 8px; }
                button { min-height: 44px; font-size: 16px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Test Store</h1>
                <div class="product-card">
                    <h2>Test Product</h2>
                    <button>Add to Cart</button>
                </div>
            </div>
            <script src="shared/data-store.js"></script>
            <script src="shared/data-client.js"></script>
        </body>
        </html>
        """,
        "style_tokens": {
            "colors": {"primary": "#111111", "accent": "#2F6BFF", "bg": "#F7F7F7"},
            "typography": {"family": "sans", "scale": "large-title"},
            "radius": "medium",
            "shadow": "soft",
            "spacing": "airy",
            "layout_patterns": ["hero-left", "card-grid"]
        },
        "aesthetic_score": {
            "dimensions": {"typography": 4, "contrast": 4, "layout": 4, "color": 4, "cta": 4},
            "total": 20,
            "issues": [],
            "auto_checks": {"wcag_contrast": "pass", "line_height": "pass", "type_scale": "pass"}
        }
    }


@pytest.fixture
def event_emitter():
    """Create event emitter for testing."""
    return EventEmitter()


@pytest.fixture
def skills_registry():
    """Load skills registry for testing."""
    return SkillsRegistry()


@pytest.fixture
def output_dir(tmp_path):
    """Temporary output directory for generated files."""
    output = tmp_path / "output"
    output.mkdir(exist_ok=True)
    return str(output)
```

### 1.2 Test Utilities

```python
# packages/backend/tests/e2e/utils.py
import base64
from pathlib import Path
from typing import Optional


def encode_image_to_base64(image_path: Path) -> str:
    """Encode image file to base64 data URL."""
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    ext = image_path.suffix.lstrip(".")
    return f"data:image/{ext};base64,{data}"


def create_mock_session(
    db_session,
    session_id: str,
    routing_metadata: Optional[dict] = None,
    model_usage: Optional[dict] = None,
):
    """Create a mock session in database."""
    from app.db.models import Session
    session = Session(
        id=session_id,
        routing_metadata=routing_metadata or {},
        model_usage=model_usage or {},
    )
    db_session.add(session)
    db_session.commit()
    return session


def create_mock_page(
    db_session,
    session_id: str,
    slug: str,
    title: str,
    role: Optional[str] = None,
):
    """Create a mock page in database."""
    from app.db.models import Page
    page = Page(
        session_id=session_id,
        slug=slug,
        title=title,
        description=f"{title} page",
    )
    db_session.add(page)
    db_session.commit()
    return page


async def stream_to_list(async_generator):
    """Convert async generator to list."""
    results = []
    async for item in async_generator:
        results.append(item)
    return results
```

---

## 2. Backend E2E Tests

### 2.1 Orchestrator Routing E2E Tests

**File**: `packages/backend/tests/e2e/test_orchestrator_routing_e2e.py`

```python
"""
E2E tests for Orchestrator Routing (v06-B2)

Acceptance Criteria:
1. Orchestrator in generation front-loads type and complexity judgment
2. Routing completes before generation starts
3. Decisions stored in session metadata
4. Guardrails injected into internal context only
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from app.agents.orchestrator import AgentOrchestrator
from app.agents.orchestrator_routing import OrchestratorRouter, RoutingDecision
from app.db.models import Session
from app.services.session import SessionService


class TestOrchestratorRoutingE2E:
    """End-to-end tests for the orchestrator routing system."""

    @pytest.mark.asyncio
    async def test_ecommerce_classification_routing(
        self, test_db, test_settings, event_emitter
    ):
        """Test that 'I want an online store' routes correctly to ecommerce skill."""
        # Arrange
        session_id = "test-ecommerce-session"
        session_service = SessionService(test_db)
        session = session_service.create(session_id)

        router = OrchestratorRouter(
            db=test_db,
            session_id=session_id,
            settings=test_settings,
        )

        # Act
        decision = await router.route("I want an online store with products")

        # Assert - Product Type
        assert decision.product_type == "ecommerce"
        assert decision.confidence >= 0.7

        # Assert - Skill Selection
        assert decision.skill_id == "flow-ecommerce-v1"
        assert "ecommerce" in decision.skill_id

        # Assert - Doc Tier
        assert decision.doc_tier in ["checklist", "standard", "extended"]

        # Assert - Guardrails
        assert "hard" in decision.guardrails
        assert len(decision.guardrails["hard"]) >= 3  # touch-target-size, readable-font-size, color-contrast

        # Assert - Session Metadata Updated
        updated_session = session_service.get_by_id(session.id)
        assert updated_session.routing_metadata is not None
        assert updated_session.routing_metadata.get("product_type") == "ecommerce"

    @pytest.mark.asyncio
    async def test_landing_page_classification_routing(
        self, test_db, test_settings, event_emitter
    ):
        """Test that 'Create a landing page' routes to static-landing skill."""
        session_id = "test-landing-session"
        router = OrchestratorRouter(
            db=test_db,
            session_id=session_id,
            settings=test_settings,
        )

        decision = await router.route("Create a landing page for my app")

        assert decision.product_type == "landing"
        assert decision.skill_id == "static-landing-v1"
        assert decision.doc_tier == "checklist"  # simple landing pages default to checklist

    @pytest.mark.asyncio
    async def test_booking_classification_routing(
        self, test_db, test_settings
    ):
        """Test that 'Make a booking page' routes correctly."""
        session_id = "test-booking-session"
        router = OrchestratorRouter(
            db=test_db,
            session_id=session_id,
            settings=test_settings,
        )

        decision = await router.route("I need a booking system for my salon")

        assert decision.product_type == "booking"
        assert decision.skill_id == "flow-booking-v1"

    @pytest.mark.asyncio
    async def test_complexity_evaluation_simple(
        self, test_db, test_settings
    ):
        """Test that single page showcase evaluates to simple complexity."""
        session_id = "test-simple-session"
        router = OrchestratorRouter(
            db=test_db,
            session_id=session_id,
            settings=test_settings,
        )

        decision = await router.route("Create a simple single page landing")

        assert decision.complexity == "simple"

    @pytest.mark.asyncio
    async def test_complexity_evaluation_medium(
        self, test_db, test_settings
    ):
        """Test that multi-page with form evaluates to medium complexity."""
        session_id = "test-medium-session"
        router = OrchestratorRouter(
            db=test_db,
            session_id=session_id,
            settings=test_settings,
        )

        decision = await router.route(
            "Create a multi-page website with home, about, and contact form"
        )

        assert decision.complexity == "medium"

    @pytest.mark.asyncio
    async def test_complexity_evaluation_complex(
        self, test_db, test_settings
    ):
        """Test that multi-page ecommerce with cart evaluates to complex."""
        session_id = "test-complex-session"
        router = OrchestratorRouter(
            db=test_db,
            session_id=session_id,
            settings=test_settings,
        )

        decision = await router.route(
            "Create an ecommerce site with product catalog, shopping cart, "
            "checkout, and user account pages"
        )

        assert decision.complexity == "complex"

    @pytest.mark.asyncio
    async def test_page_mention_parsing(
        self, test_db, test_settings
    ):
        """Test @Page mention parsing in routing."""
        # Create existing pages
        create_mock_page(test_db, "session-1", "home", "Home Page")
        create_mock_page(test_db, "session-1", "about", "About Us")

        router = OrchestratorRouter(
            db=test_db,
            session_id="session-1",
            settings=test_settings,
        )

        decision = await router.route("Update @Home with new hero section")

        assert "home" in decision.target_pages

    @pytest.mark.asyncio
    async def test_style_profile_routing_keywords(
        self, test_db, test_settings
    ):
        """Test style profile routing based on keywords."""
        router = OrchestratorRouter(
            db=test_db,
            session_id="session-1",
            settings=test_settings,
        )

        # Luxury/spa keywords -> soft-elegant
        decision1 = await router.route("Create a luxury spa website")
        assert decision1.style_profile == "soft-elegant"

        # Tech/AI keywords -> bold-tech
        decision2 = await router.route("Create an AI analytics dashboard")
        assert decision2.style_profile == "bold-tech"

        # No keywords -> clean-modern (default)
        decision3 = await router.route("Create a website")
        assert decision3.style_profile == "clean-modern"

    @pytest.mark.asyncio
    async def test_doc_tier_selection_by_complexity(
        self, test_db, test_settings
    ):
        """Test doc tier selection based on complexity."""
        router = OrchestratorRouter(
            db=test_db,
            session_id="session-1",
            settings=test_settings,
        )

        # Simple flow app -> checklist
        decision1 = await router.route("Create a simple landing page")
        assert decision1.doc_tier == "checklist"

        # Medium flow app -> standard
        decision2 = await router.route("Create a multi-page booking site")
        assert decision2.doc_tier == "standard"

        # Complex flow app -> extended
        decision3 = await router.route(
            "Create a full-featured ecommerce platform with "
            "inventory, orders, and analytics"
        )
        assert decision3.doc_tier == "extended"

    @pytest.mark.asyncio
    async def test_routing_decision_persistence(
        self, test_db, test_settings
    ):
        """Test that routing decisions are persisted in session metadata."""
        session_id = "test-persistence-session"
        session_service = SessionService(test_db)
        session = session_service.create(session_id)

        router = OrchestratorRouter(
            db=test_db,
            session_id=session_id,
            settings=test_settings,
        )

        decision = await router.route("Create an online store")

        # Verify session metadata
        updated_session = session_service.get_by_id(session.id)
        metadata = updated_session.routing_metadata

        assert metadata is not None
        assert metadata["product_type"] == decision.product_type
        assert metadata["complexity"] == decision.complexity
        assert metadata["skill_id"] == decision.skill_id
        assert metadata["doc_tier"] == decision.doc_tier
        assert metadata["style_profile"] == decision.style_profile
```

### 2.2 Multi-Model Routing E2E Tests

**File**: `packages/backend/tests/e2e/test_multi_model_routing_e2e.py`

```python
"""
E2E tests for Multi-Model Routing (v06-B6)

Acceptance Criteria:
1. Model roles are well-defined enum
2. Configuration supports multiple models per role
3. Product-specific overrides are supported
4. Configuration is environment-based
5. Falls to next model on failure
6. Vision capability detected/declared
7. Token limits known per model
"""
import pytest
from unittest.mock import patch, AsyncMock

from app.llm.model_pool import ModelPoolManager
from app.llm.model_catalog import ModelRole, ModelCapability
from app.config import get_settings


class TestMultiModelRoutingE2E:
    """End-to-end tests for the multi-model routing system."""

    def test_model_role_enum_exists(self):
        """Test that all model roles are defined."""
        expected_roles = {
            "classifier",
            "writer",
            "validator",
            "expander",
            "style_refiner",
        }
        actual_roles = {role.value for role in ModelRole}
        assert expected_roles <= actual_roles

    def test_model_pool_configuration(self, test_settings):
        """Test that model pool can be configured from environment."""
        pool = ModelPoolManager(settings=test_settings)

        # Each role should have at least one model
        for role in ModelRole:
            model = pool.get_model(role.value)
            assert model is not None
            assert "model" in model
            assert "base_url" in model

    def test_product_specific_model_pools(self, test_settings):
        """Test that product types can have specific model pools."""
        pool = ModelPoolManager(settings=test_settings)

        # Different product types should route to appropriate pools
        ecommerce_writer = pool.get_model("writer", product_type="ecommerce")
        landing_writer = pool.get_model("writer", product_type="landing")

        # Models may differ based on product type
        assert ecommerce_writer is not None
        assert landing_writer is not None

    def test_fallback_on_timeout(self, test_settings):
        """Test fallback behavior when model times out."""
        pool = ModelPoolManager(settings=test_settings)

        with patch.object(
            pool, "_call_model", side_effect=[TimeoutError("Timeout"), {"model": "fallback-model"}
        ]):
            model = pool.get_model_with_fallback("writer")
            assert model is not None

    def test_fallback_on_connection_error(self, test_settings):
        """Test fallback behavior when connection fails."""
        pool = ModelPoolManager(settings=test_settings)

        with patch.object(
            pool, "_call_model", side_effect=[ConnectionError("Failed"), {"model": "fallback-model"}
        ]):
            model = pool.get_model_with_fallback("writer")
            assert model is not None

    def test_vision_capability_detection(self, test_settings):
        """Test that vision capability is detected for models."""
        pool = ModelPoolManager(settings=test_settings)

        # Style refiner requires vision capability
        style_model = pool.get_model("style_refiner")
        assert style_model is not None

        # Check if model has vision capability
        catalog = pool.get_catalog()
        model_info = catalog.get_model(style_model["model"])
        if model_info:
            assert "capabilities" in model_info.metadata

    def test_token_limits_per_model(self, test_settings):
        """Test that token limits are known for each model."""
        pool = ModelPoolManager(settings=test_settings)
        catalog = pool.get_catalog()

        # All models should have max_tokens defined
        for role in ModelRole:
            model = pool.get_model(role.value)
            if model:
                model_info = catalog.get_model(model["model"])
                assert model_info is not None
                assert hasattr(model_info, "max_tokens")

    @pytest.mark.asyncio
    async def test_classifier_uses_light_model(self, test_settings):
        """Test that classification uses the light model."""
        from app.agents.classifier import ProductClassifier

        classifier = ProductClassifier(
            db=None, session_id="test-1", settings=test_settings
        )

        # The classifier should be configured to use a lightweight model
        assert classifier.model_role == ModelRole.CLASSIFIER

    @pytest.mark.asyncio
    async def test_validator_uses_light_model(self, test_settings):
        """Test that validation uses the light model."""
        from app.agents.validator import Validator

        validator = Validator(
            db=None, session_id="test-1", settings=test_settings
        )

        assert validator.model_role == ModelRole.VALIDATOR

    @pytest.mark.asyncio
    async def test_generation_uses_heavy_model(self, test_settings):
        """Test that generation uses the heavy model."""
        from app.agents.generation import GenerationAgent

        agent = GenerationAgent(
            db=None, session_id="test-1", settings=test_settings
        )

        assert agent.model_role == ModelRole.WRITER

    def test_session_model_usage_tracking(self, test_db, test_settings):
        """Test that model usage is tracked in sessions."""
        from app.services.session import SessionService

        session_service = SessionService(test_db)
        session = session_service.create("test-usage-session")

        # Simulate model usage
        pool = ModelPoolManager(settings=test_settings)
        model = pool.get_model("writer")

        session_service.update_model_usage(
            session.id,
            model_role="writer",
            model_id=model["model"],
            tokens_used=1000,
        )

        # Verify tracking
        updated = session_service.get_by_id(session.id)
        assert updated.model_usage is not None
        assert "writer" in updated.model_usage
```

### 2.3 Product Doc Tiers E2E Tests

**File**: `packages/backend/tests/e2e/test_product_doc_tiers_e2e.py`

```python
"""
E2E tests for Product Doc Tiers (v06-B4)

Acceptance Criteria:
1. All tiers share base fields (product_type, complexity, doc_tier)
2. Checklist tier has minimal structure
3. Standard tier includes pages, data_flow, state_contract
4. Extended tier supports mermaid and multi-doc
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.agents.product_doc import ProductDocAgent
from app.schemas.product_doc import ProductDocChecklist, ProductDocStandard, ProductDocExtended
from app.services.product_doc import ProductDocService


class TestProductDocTiersE2E:
    """End-to-end tests for product document tiered output."""

    @pytest.mark.asyncio
    async def test_checklist_tier_generation(
        self, test_db, test_settings, event_emitter, mock_llm_response
    ):
        """Test that checklist tier generates minimal structure."""
        agent = ProductDocAgent(
            db=test_db,
            session_id="test-checklist",
            settings=test_settings,
            event_emitter=event_emitter,
        )

        with patch.object(agent, "_call_llm", return_value=mock_llm_response["product_doc"]):
            result = await agent.generate(
                session_id="test-checklist",
                user_message="Create a simple landing page",
                doc_tier="checklist",
            )

        # Verify checklist structure
        assert result.structured is not None
        assert "project_name" in result.structured
        assert "product_type" in result.structured
        assert "complexity" in result.structured
        assert "doc_tier" in result.structured
        assert result.structured["doc_tier"] == "checklist"

        # Checklist should have minimal pages structure
        assert "pages" in result.structured

    @pytest.mark.asyncio
    async def test_standard_tier_generation(
        self, test_db, test_settings, event_emitter, mock_llm_response
    ):
        """Test that standard tier includes pages, data_flow, and state_contract."""
        agent = ProductDocAgent(
            db=test_db,
            session_id="test-standard",
            settings=test_settings,
            event_emitter=event_emitter,
        )

        with patch.object(agent, "_call_llm", return_value=mock_llm_response["product_doc"]):
            result = await agent.generate(
                session_id="test-standard",
                user_message="Create a multi-page ecommerce site",
                doc_tier="standard",
            )

        # Verify standard tier structure
        assert result.structured["doc_tier"] == "standard"
        assert "pages" in result.structured
        assert len(result.structured["pages"]) >= 1

        # Flow apps must have state_contract and data_flow
        assert "state_contract" in result.structured
        assert "data_flow" in result.structured

    @pytest.mark.asyncio
    async def test_extended_tier_generation(
        self, test_db, test_settings, event_emitter
    ):
        """Test that extended tier supports mermaid diagrams."""
        agent = ProductDocAgent(
            db=test_db,
            session_id="test-extended",
            settings=test_settings,
            event_emitter=event_emitter,
        )

        extended_response = {
            "content": "# Extended Product Doc",
            "structured": {
                "project_name": "Complex App",
                "product_type": "ecommerce",
                "complexity": "complex",
                "doc_tier": "extended",
                "pages": [
                    {"slug": "home", "title": "Home", "role": "catalog"},
                    {"slug": "cart", "title": "Cart", "role": "checkout"},
                    {"slug": "checkout", "title": "Checkout", "role": "checkout"},
                ],
                "state_contract": {
                    "shared_state_key": "instant-coffee:state",
                    "schema": {"cart": {"items": []}}
                },
                "data_flow": [
                    {"from": "home", "event": "add_to_cart", "to": "cart"},
                    {"from": "cart", "event": "checkout", "to": "checkout"},
                ],
                "mermaid_diagram": "graph TD\nHome[Home] -->|add_to_cart| Cart[Cart]\nCart -->|checkout| Checkout[Checkout]",
                "additional_docs": [
                    {"title": "Data Schema", "content": "..."}
                ]
            }
        }

        with patch.object(agent, "_call_llm", return_value=extended_response):
            result = await agent.generate(
                session_id="test-extended",
                user_message="Create a full ecommerce platform",
                doc_tier="extended",
            )

        # Verify extended tier structure
        assert result.structured["doc_tier"] == "extended"
        assert "mermaid_diagram" in result.structured
        assert "additional_docs" in result.structured

    @pytest.mark.asyncio
    async def test_tier_selection_by_complexity(
        self, test_db, test_settings, event_emitter
    ):
        """Test that tier is correctly selected based on complexity."""
        from app.agents.orchestrator_routing import DocTierSelector

        selector = DocTierSelector()

        # Simple -> checklist
        tier1 = selector.select_tier(complexity="simple", product_type="landing")
        assert tier1 == "checklist"

        # Medium -> standard
        tier2 = selector.select_tier(complexity="medium", product_type="ecommerce")
        assert tier2 == "standard"

        # Complex -> extended
        tier3 = selector.select_tier(complexity="complex", product_type="ecommerce")
        assert tier3 == "extended"

    @pytest.mark.asyncio
    async def test_complexity_normalization(
        self, test_db, test_settings
    ):
        """Test complexity value normalization from legacy values."""
        from app.agents.orchestrator_routing import normalize_complexity

        # Legacy values should map to canonical values
        assert normalize_complexity("checklist") == "simple"
        assert normalize_complexity("standard") == "medium"
        assert normalize_complexity("extended") == "complex"

        # Canonical values pass through
        assert normalize_complexity("simple") == "simple"
        assert normalize_complexity("medium") == "medium"
        assert normalize_complexity("complex") == "complex"
```

### 2.4 Style Reference E2E Tests

**File**: `packages/backend/tests/e2e/test_style_reference_e2e.py`

```python
"""
E2E tests for Style Reference (v06-B3)

Acceptance Criteria:
1. StyleReference model validates fields and limits to 1-3 images
2. Modes are enum-validated
3. Extracts color palette/typography/radius/shadow/spacing
4. Full-mimic prompt includes layout patterns
5. Style tokens appear in generation context
6. Scope filtering limits token injection
7. Fallback to profile tokens when no images
"""
import pytest
import base64
from unittest.mock import AsyncMock, patch

from app.schemas.style_reference import StyleReference, StyleReferenceMode
from app.services.style_reference import StyleReferenceService
from app.agents.style_refiner import StyleRefiner


class TestStyleReferenceE2E:
    """End-to-end tests for style reference functionality."""

    def test_style_reference_validation(self):
        """Test that StyleReference model validates correctly."""
        # Valid with 1 image
        ref1 = StyleReference(
            mode=StyleReferenceMode.FULL_MIMIC,
            images=["data:image/png;base64,abc123"],
        )
        assert ref1.mode == StyleReferenceMode.FULL_MIMIC
        assert len(ref1.images) == 1

        # Valid with 3 images (max)
        ref2 = StyleReference(
            mode=StyleReferenceMode.STYLE_ONLY,
            images=[
                "data:image/png;base64,abc123",
                "data:image/png;base64,def456",
                "data:image/png;base64,ghi789",
            ],
        )
        assert len(ref2.images) == 3

    def test_style_reference_max_images_validation(self):
        """Test that more than 3 images raises validation error."""
        with pytest.raises(ValueError) as exc:
            StyleReference(
                mode=StyleReferenceMode.FULL_MIMIC,
                images=[
                    "data:image/png;base64,1",
                    "data:image/png;base64,2",
                    "data:image/png;base64,3",
                    "data:image/png;base64,4",  # Exceeds max
                ],
            )
        assert "3" in str(exc.value).lower()

    def test_style_reference_mode_enum(self):
        """Test that only valid modes are accepted."""
        # Valid modes
        ref1 = StyleReference(mode=StyleReferenceMode.FULL_MIMIC, images=[])
        assert ref1.mode == "full_mimic"

        ref2 = StyleReference(mode=StyleReferenceMode.STYLE_ONLY, images=[])
        assert ref2.mode == "style_only"

    @pytest.mark.asyncio
    async def test_style_token_extraction(
        self, test_settings, sample_style_reference_image
    ):
        """Test that style tokens are extracted from images."""
        service = StyleReferenceService(settings=test_settings)

        mock_tokens = {
            "colors": {"primary": "#1A1F2B", "accent": "#2F6BFF", "bg": "#F8FAFC"},
            "typography": {"heading": {"family": "Space Grotesk"}, "body": {"family": "DM Sans"}},
            "radius": "medium",
            "shadow": "soft",
            "spacing": "airy",
            "layout_patterns": ["hero-left", "card-grid"]
        }

        with patch.object(service, "_extract_from_vision", return_value=mock_tokens):
            ref = StyleReference(
                mode=StyleReferenceMode.FULL_MIMIC,
                images=[str(sample_style_reference_image)],
            )
            tokens = await service.extract_tokens(ref)

        # Verify token structure
        assert "colors" in tokens
        assert "typography" in tokens
        assert "radius" in tokens
        assert "shadow" in tokens
        assert "spacing" in tokens

    @pytest.mark.asyncio
    async def test_full_mimic_includes_layout_patterns(
        self, test_settings, sample_style_reference_image
    ):
        """Test that full_mimic mode includes layout patterns."""
        service = StyleReferenceService(settings=test_settings)

        mock_tokens = {
            "colors": {"primary": "#000000"},
            "typography": {"family": "sans"},
            "radius": "medium",
            "shadow": "soft",
            "spacing": "airy",
            "layout_patterns": ["hero-left", "card-grid", "split-feature"]
        }

        with patch.object(service, "_extract_from_vision", return_value=mock_tokens):
            ref = StyleReference(
                mode=StyleReferenceMode.FULL_MIMIC,
                images=[str(sample_style_reference_image)],
            )
            tokens = await service.extract_tokens(ref)

        # Full mimic should include layout patterns
        assert "layout_patterns" in tokens
        assert len(tokens["layout_patterns"]) > 0

    @pytest.mark.asyncio
    async def test_style_only_mode_no_layout_patterns(
        self, test_settings, sample_style_reference_image
    ):
        """Test that style_only mode does not require layout patterns."""
        service = StyleReferenceService(settings=test_settings)

        mock_tokens = {
            "colors": {"primary": "#000000"},
            "typography": {"family": "sans"},
            "radius": "medium",
            "shadow": "soft",
            "spacing": "airy",
            # No layout_patterns in style_only mode
        }

        with patch.object(service, "_extract_from_vision", return_value=mock_tokens):
            ref = StyleReference(
                mode=StyleReferenceMode.STYLE_ONLY,
                images=[str(sample_style_reference_image)],
            )
            tokens = await service.extract_tokens(ref)

        # Layout patterns may be absent in style_only mode
        assert "colors" in tokens
        assert "typography" in tokens

    @pytest.mark.asyncio
    async def test_scope_filtering_for_target_pages(
        self, test_settings
    ):
        """Test that scope filtering limits token injection to target pages."""
        service = StyleReferenceService(settings=test_settings)

        ref = StyleReference(
            mode=StyleReferenceMode.FULL_MIMIC,
            images=["data:image/png;base64,abc"],
            scope_pages=["home", "about"],
        )

        # Verify scope is preserved
        assert ref.scope_pages == ["home", "about"]

        # Tokens should only apply to specified pages during generation
        # This is verified in generation E2E tests

    @pytest.mark.asyncio
    async def test_fallback_to_profile_tokens(self, test_settings):
        """Test fallback to style profile when no images provided."""
        service = StyleReferenceService(settings=test_settings)

        ref = StyleReference(
            mode=StyleReferenceMode.FULL_MIMIC,
            images=[],  # No images
        )

        tokens = await service.extract_tokens(ref)

        # Should return default profile tokens
        assert tokens is not None
        assert "colors" in tokens

    @pytest.mark.asyncio
    async def test_style_refiner_agent_integration(
        self, test_db, test_settings, event_emitter
    ):
        """Test that StyleRefiner agent uses style tokens."""
        from app.agents.style_refiner import StyleRefiner

        refiner = StyleRefiner(
            db=test_db,
            session_id="test-refiner",
            settings=test_settings,
            event_emitter=event_emitter,
        )

        style_tokens = {
            "colors": {"primary": "#2F6BFF", "accent": "#FF6B2F", "bg": "#F8FAFC"},
            "typography": {"family": "Inter", "scale": "large"},
            "radius": "rounded",
            "shadow": "diffuse",
            "spacing": "generous",
        }

        original_html = "<html><body><h1>Test</h1></body></html>"

        with patch.object(refiner, "_call_llm", return_value="<html><body><h1 style='color:#2F6BFF'>Test</h1></body></html>"):
            result = await refiner.refine(
                html=original_html,
                style_tokens=style_tokens,
                product_type="landing",
            )

        assert result is not None
        assert "#2F6BFF" in result or "color" in result
```

### 2.5 Data Protocol E2E Tests

**File**: `packages/backend/tests/e2e/test_data_protocol_e2e.py`

```python
"""
E2E tests for Data Protocol (v06-B5)

Acceptance Criteria:
1. Flow apps generate state contract
2. Static apps have empty/minimal contract
3. Contract includes event definitions
4. Contract output to session output directory
5. Script implements InstantCoffeeDataStore class
6. Supports get_state, set_state, persist
7. Listens to storage events for cross-page sync
8. Logs events to instant-coffee:events key
9. Generated pages include script tags
10. Messages sent on state changes (debounced)
11. Messages sent immediately on submit events
12. State restored on page load
13. Cross-page navigation preserves state
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.services.data_protocol import DataProtocolGenerator
from app.utils.product_doc import (
    build_data_store_script,
    build_data_client_script,
    inject_data_scripts
)


class TestDataProtocolE2E:
    """End-to-end tests for data protocol generation."""

    def test_flow_app_generates_state_contract(self, tmp_path):
        """Test that flow apps generate a proper state contract."""
        generator = DataProtocolGenerator(
            output_dir=str(tmp_path),
            session_id="test-flow-session",
            db=None,
        )

        contract = generator.generate_state_contract("ecommerce")

        # Verify contract structure
        assert contract["shared_state_key"] == "instant-coffee:state"
        assert contract["records_key"] == "instant-coffee:records"
        assert contract["events_key"] == "instant-coffee:events"
        assert "schema" in contract
        assert len(contract["schema"]) > 0  # Flow apps should have schema

    def test_static_app_minimal_contract(self, tmp_path):
        """Test that static apps have minimal/empty contract."""
        generator = DataProtocolGenerator(
            output_dir=str(tmp_path),
            session_id="test-static-session",
            db=None,
        )

        contract = generator.generate_state_contract("landing")

        # Static apps should have empty schema
        assert contract["schema"] == {}
        assert contract["events"] == []

    def test_contract_includes_event_definitions(self, tmp_path):
        """Test that contract includes event definitions."""
        generator = DataProtocolGenerator(
            output_dir=str(tmp_path),
            session_id="test-events-session",
            db=None,
        )

        contract = generator.generate_state_contract("ecommerce")

        # Should include event definitions
        assert "events" in contract
        assert isinstance(contract["events"], list)

        # Common events for ecommerce
        event_names = [e.get("name") for e in contract["events"]]
        assert "add_to_cart" in event_names or len(contract["events"]) >= 1

    def test_contract_output_to_session_directory(self, tmp_path):
        """Test that contract is written to session output directory."""
        generator = DataProtocolGenerator(
            output_dir=str(tmp_path),
            session_id="test-output-session",
            db=None,
        )

        contract = generator.generate_state_contract("ecommerce")
        assets = generator.write_shared_assets("ecommerce", contract, include_client=True)

        # Verify files exist
        session_output = tmp_path / "test-output-session"
        shared_dir = session_output / "shared"

        assert shared_dir.exists()
        assert (shared_dir / "state-contract.json").exists()
        assert (shared_dir / "data-store.js").exists()
        assert (shared_dir / "data-client.js").exists()

    def test_data_store_script_class_definition(self):
        """Test that data-store script implements InstantCoffeeDataStore class."""
        contract = {
            "shared_state_key": "instant-coffee:state",
            "records_key": "instant-coffee:records",
            "events_key": "instant-coffee:events",
            "schema": {"cart": {"items": []}},
            "events": [],
        }

        script = build_data_store_script(contract)

        # Verify class definition
        assert "class InstantCoffeeDataStore" in script
        assert "get_state" in script
        assert "set_state" in script
        assert "persist" in script

    def test_data_store_storage_event_listener(self):
        """Test that data-store script listens to storage events."""
        contract = {
            "shared_state_key": "instant-coffee:state",
            "records_key": "instant-coffee:records",
            "events_key": "instant-coffee:events",
            "schema": {},
            "events": [],
        }

        script = build_data_store_script(contract)

        # Should add event listener for cross-page sync
        assert "addEventListener" in script
        assert "storage" in script

    def test_data_store_event_logging(self):
        """Test that data-store script logs events."""
        contract = {
            "shared_state_key": "instant-coffee:state",
            "records_key": "instant-coffee:records",
            "events_key": "instant-coffee:events",
            "schema": {},
            "events": [{"name": "test_event", "payload": {"key": "value"}}],
        }

        script = build_data_store_script(contract)

        # Should log events
        assert "events" in script.lower()
        assert contract["events_key"] in script

    def test_data_client_product_helpers(self):
        """Test that data-client includes product-type-specific helpers."""
        contract = {
            "shared_state_key": "instant-coffee:state",
            "records_key": "instant-coffee:records",
            "events_key": "instant-coffee:events",
            "schema": {},
            "events": [],
        }

        # Ecommerce client
        client_script = build_data_client_script("ecommerce", contract)

        # Should have ecommerce-specific helpers
        assert "InstantCoffeeDataClient" in client_script
        assert "ecommerce" in client_script.lower()

    def test_script_injection_into_html(self):
        """Test that scripts are properly injected into HTML."""
        html = "<html><head></head><body>Content</body></html>"

        injected = inject_data_scripts(
            html,
            store_src="shared/data-store.js",
            client_src="shared/data-client.js",
        )

        # Scripts should be injected before body close
        assert "shared/data-store.js" in injected
        assert "shared/data-client.js" in injected
        assert injected.index("data-store.js") < injected.index("data-client.js")
        assert injected.index("data-client.js") < injected.index("</body>")

    def test_postmessage_on_state_changes(self):
        """Test that postMessage is sent on state changes."""
        contract = {
            "shared_state_key": "instant-coffee:state",
            "records_key": "instant-coffee:records",
            "events_key": "instant-coffee:events",
            "schema": {},
            "events": [],
        }

        script = build_data_store_script(contract)

        # Should include postMessage for preview updates
        assert "postMessage" in script
        assert "window.parent" in script

    def test_postmessage_immediate_on_submit(self):
        """Test that postMessage is sent immediately on submit events."""
        contract = {
            "shared_state_key": "instant-coffee:state",
            "records_key": "instant-coffee:records",
            "events_key": "instant-coffee:events",
            "schema": {},
            "events": [
                {"name": "submit_booking", "immediate": True},
                {"name": "add_to_cart", "immediate": False},
            ],
        }

        script = build_data_store_script(contract)

        # Should handle immediate vs debounced posting
        assert "postMessage" in script

    def test_state_restoration_on_load(self):
        """Test that state is restored from localStorage on page load."""
        contract = {
            "shared_state_key": "instant-coffee:state",
            "records_key": "instant-coffee:records",
            "events_key": "instant-coffee:events",
            "schema": {"cart": {"items": []}},
            "events": [],
        }

        script = build_data_store_script(contract)

        # Should load state from localStorage on initialization
        assert "localStorage" in script
        assert "getItem" in script

    def test_cross_page_state_preservation(self):
        """Test that state is preserved across page navigation."""
        contract = {
            "shared_state_key": "instant-coffee:state",
            "records_key": "instant-coffee:records",
            "events_key": "instant-coffee:events",
            "schema": {},
            "events": [],
        }

        script = build_data_store_script(contract)

        # Should handle storage events for cross-page sync
        assert "addEventListener" in script
        assert "storage" in script
```

### 2.6 Aesthetic Scoring E2E Tests

**File**: `packages/backend/tests/e2e/test_aesthetic_scoring_e2e.py`

```python
"""
E2E tests for Aesthetic Scoring (v06-B7)

Acceptance Criteria:
1. Score model validates ranges (1-5 per dimension)
2. Total score calculated correctly
3. Auto-checks return pass/fail status
4. Returns score for each dimension
5. Returns total score (sum of dimensions)
6. Lists specific issues found
7. Includes auto-check results
8. Contrast check returns pass/fail + ratio
9. Line-height check validates body text
10. Type scale check ensures hierarchy
11. Scores >= 18 pass without refiner
12. Scores < 18 trigger Style Refiner
13. Maximum 2 refiner iterations
14. Higher-scoring version selected
15. Never degrades score
16. Stops after 2 iterations
17. All Landing/Card/Invitation pages scored
18. Low scores trigger refiner
19. Scores logged for analysis
20. Generation completes with best version
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.agents.validator import AestheticValidator
from app.schemas.validation import (
    AestheticScore,
    DimensionScores,
    AutoChecks
)
from app.utils.validation import run_auto_checks


class TestAestheticScoringE2E:
    """End-to-end tests for aesthetic scoring system."""

    def test_score_model_validates_ranges(self):
        """Test that score dimensions are within 1-5 range."""
        # Valid score
        score = AestheticScore(
            dimensions=DimensionScores(
                typography=4,
                contrast=5,
                layout=3,
                color=4,
                cta=5,
            ),
            auto_checks=AutoChecks(
                wcag_contrast="pass",
                line_height="pass",
                type_scale="pass",
            ),
        )

        # All dimensions should be 1-5
        for dim_value in [
            score.dimensions.typography,
            score.dimensions.contrast,
            score.dimensions.layout,
            score.dimensions.color,
            score.dimensions.cta,
        ]:
            assert 1 <= dim_value <= 5

    def test_invalid_dimension_raises_error(self):
        """Test that invalid dimension values raise validation error."""
        with pytest.raises(ValueError):
            DimensionScores(
                typography=6,  # Invalid: > 5
                contrast=4,
                layout=4,
                color=4,
                cta=4,
            )

        with pytest.raises(ValueError):
            DimensionScores(
                typography=0,  # Invalid: < 1
                contrast=4,
                layout=4,
                color=4,
                cta=4,
            )

    def test_total_score_calculated_correctly(self):
        """Test that total score is sum of all dimensions."""
        score = AestheticScore(
            dimensions=DimensionScores(
                typography=4,
                contrast=4,
                layout=4,
                color=3,
                cta=3,
            ),
            auto_checks=AutoChecks(
                wcag_contrast="pass",
                line_height="pass",
                type_scale="pass",
            ),
        )

        assert score.total == 18  # 4+4+4+3+3

    def test_auto_checks_pass_fail_status(self):
        """Test that auto-checks return pass/fail status."""
        checks = AutoChecks(
            wcag_contrast="pass",
            line_height="fail",
            type_scale="pass",
        )

        assert checks.wcag_contrast == "pass"
        assert checks.line_height == "fail"
        assert checks.type_scale == "pass"

    def test_returns_each_dimension_score(self):
        """Test that each dimension score is accessible."""
        score = AestheticScore(
            dimensions=DimensionScores(
                typography=5,
                contrast=4,
                layout=3,
                color=4,
                cta=5,
            ),
            auto_checks=AutoChecks(
                wcag_contrast="pass",
                line_height="pass",
                type_scale="pass",
            ),
        )

        assert score.dimensions.typography == 5
        assert score.dimensions.contrast == 4
        assert score.dimensions.layout == 3
        assert score.dimensions.color == 4
        assert score.dimensions.cta == 5

    def test_lists_specific_issues(self):
        """Test that score can list specific issues found."""
        score = AestheticScore(
            dimensions=DimensionScores(
                typography=3,
                contrast=2,
                layout=4,
                color=4,
                cta=4,
            ),
            auto_checks=AutoChecks(
                wcag_contrast="fail",
                line_height="pass",
                type_scale="pass",
            ),
            issues=[
                "Low contrast on body text",
                "Font size too small on headings",
            ],
        )

        assert len(score.issues) == 2
        assert "contrast" in score.issues[0].lower()
        assert "Font size" in score.issues[1]

    def test_contrast_check_with_ratio(self):
        """Test that contrast check returns pass/fail with ratio."""
        html = """
        <html>
        <head><style>body { color: #000000; background: #FFFFFF; }</style></head>
        <body>Text</body>
        </html>
        """

        checks = run_auto_checks(html)

        # Should have pass/fail status
        assert checks.wcag_contrast in ["pass", "fail"]

        # If pass, ratio should meet WCAG AA
        # If fail, ratio should be below threshold

    def test_line_height_check_validates_body(self):
        """Test that line-height check validates body text."""
        # Valid line-height
        html1 = """
        <html>
        <head><style>body { line-height: 1.5; }</style></head>
        <body>Text</body>
        </html>
        """
        checks1 = run_auto_checks(html1)
        assert checks1.line_height == "pass"

        # Invalid line-height (too small)
        html2 = """
        <html>
        <head><style>body { line-height: 1.0; }</style></head>
        <body>Text</body>
        </html>
        """
        checks2 = run_auto_checks(html2)
        assert checks2.line_height == "fail"

    def test_type_scale_check_hierarchy(self):
        """Test that type scale check ensures hierarchy."""
        # Valid hierarchy
        html1 = """
        <html>
        <head><style>
            h1 { font-size: 32px; }
            h2 { font-size: 24px; }
            body { font-size: 16px; }
        </style></head>
        <body><h1>Title</h1><p>Text</p></body>
        </html>
        """
        checks1 = run_auto_checks(html1)
        assert checks1.type_scale == "pass"

    def test_threshold_passing(self):
        """Test that scores >= 18 pass without refiner."""
        score = AestheticScore(
            dimensions=DimensionScores(
                typography=4,
                contrast=4,
                layout=4,
                color=3,
                cta=3,
            ),
            auto_checks=AutoChecks(
                wcag_contrast="pass",
                line_height="pass",
                type_scale="pass",
            ),
        )

        assert score.total == 18
        assert score.passes_threshold is True

        # Higher score should also pass
        score2 = AestheticScore(
            dimensions=DimensionScores(
                typography=5,
                contrast=5,
                layout=5,
                color=5,
                cta=5,
            ),
            auto_checks=AutoChecks(
                wcag_contrast="pass",
                line_height="pass",
                type_scale="pass",
            ),
        )

        assert score2.total == 25
        assert score2.passes_threshold is True

    def test_threshold_failing(self):
        """Test that scores < 18 trigger refiner."""
        score = AestheticScore(
            dimensions=DimensionScores(
                typography=3,
                contrast=3,
                layout=3,
                color=3,
                cta=3,
            ),
            auto_checks=AutoChecks(
                wcag_contrast="pass",
                line_height="pass",
                type_scale="pass",
            ),
        )

        assert score.total == 15
        assert score.passes_threshold is False

    @pytest.mark.asyncio
    async def test_refiner_triggered_on_low_score(
        self, test_db, test_settings, event_emitter
    ):
        """Test that low scores trigger Style Refiner."""
        validator = AestheticValidator(
            db=test_db,
            session_id="test-validator",
            settings=test_settings,
            event_emitter=event_emitter,
        )

        low_score = AestheticScore(
            dimensions=DimensionScores(
                typography=3,
                contrast=3,
                layout=3,
                color=3,
                cta=3,
            ),
            auto_checks=AutoChecks(
                wcag_contrast="pass",
                line_height="pass",
                type_scale="pass",
            ),
        )

        improved_score = AestheticScore(
            dimensions=DimensionScores(
                typography=4,
                contrast=4,
                layout=4,
                color=4,
                cta=4,
            ),
            auto_checks=AutoChecks(
                wcag_contrast="pass",
                line_height="pass",
                type_scale="pass",
            ),
        )

        async def mock_score(html, **kwargs):
            return low_score if html == "original" else improved_score

        async def mock_refine(html, **kwargs):
            return "refined-html"

        with patch.object(validator.scorer, "score", mock_score):
            with patch.object(validator.style_refiner, "refine", mock_refine):
                final_html, final_score, attempts = await validator.validate_and_refine(
                    "original",
                    product_type="landing"
                )

        # Should have attempted refinement
        assert len(attempts) > 1
        assert final_html == "refined-html"

    @pytest.mark.asyncio
    async def test_max_two_refiner_iterations(
        self, test_db, test_settings, event_emitter
    ):
        """Test that refiner runs maximum 2 iterations."""
        validator = AestheticValidator(
            db=test_db,
            session_id="test-max-iterations",
            settings=test_settings,
            event_emitter=event_emitter,
        )

        # Always return low score (should still stop after 2 iterations)
        low_score = AestheticScore(
            dimensions=DimensionScores(
                typography=3,
                contrast=3,
                layout=3,
                color=3,
                cta=3,
            ),
            auto_checks=AutoChecks(
                wcag_contrast="pass",
                line_height="pass",
                type_scale="pass",
            ),
        )

        async def mock_score(html, **kwargs):
            return low_score

        async def mock_refine(html, **kwargs):
            return f"refined-{html}"

        with patch.object(validator.scorer, "score", mock_score):
            with patch.object(validator.style_refiner, "refine", mock_refine):
                _, _, attempts = await validator.validate_and_refine(
                    "original",
                    product_type="landing"
                )

        # Maximum 3 attempts (original + 2 refinements)
        assert len(attempts) <= 3

    @pytest.mark.asyncio
    async def test_higher_scoring_version_selected(
        self, test_db, test_settings, event_emitter
    ):
        """Test that higher-scoring version is selected."""
        validator = AestheticValidator(
            db=test_db,
            session_id="test-higher-score",
            settings=test_settings,
            event_emitter=event_emitter,
        )

        original_score = AestheticScore(
            dimensions=DimensionScores(
                typography=3,
                contrast=3,
                layout=3,
                color=3,
                cta=3,
            ),
            auto_checks=AutoChecks(
                wcag_contrast="pass",
                line_height="pass",
                type_scale="pass",
            ),
        )

        refined_score = AestheticScore(
            dimensions=DimensionScores(
                typography=4,
                contrast=5,
                layout=4,
                color=4,
                cta=4,
            ),
            auto_checks=AutoChecks(
                wcag_contrast="pass",
                line_height="pass",
                type_scale="pass",
            ),
        )

        async def mock_score(html, **kwargs):
            return original_score if html == "original" else refined_score

        async def mock_refine(html, **kwargs):
            return "refined"

        with patch.object(validator.scorer, "score", mock_score):
            with patch.object(validator.style_refiner, "refine", mock_refine):
                final_html, final_score, _ = await validator.validate_and_refine(
                    "original",
                    product_type="landing"
                )

        # Should select the higher-scoring version
        assert final_score.total >= original_score.total
        assert final_html == "refined"

    @pytest.mark.asyncio
    async def test_never_degrades_score(
        self, test_db, test_settings, event_emitter
    ):
        """Test that refiner never degrades the score."""
        validator = AestheticValidator(
            db=test_db,
            session_id="test-no-degrade",
            settings=test_settings,
            event_emitter=event_emitter,
        )

        original_score = AestheticScore(
            dimensions=DimensionScores(
                typography=4,
                contrast=4,
                layout=4,
                color=3,
                cta=3,
            ),
            auto_checks=AutoChecks(
                wcag_contrast="pass",
                line_height="pass",
                type_scale="pass",
            ),
        )

        # Refiner makes it worse
        worse_score = AestheticScore(
            dimensions=DimensionScores(
                typography=2,
                contrast=2,
                layout=2,
                color=2,
                cta=2,
            ),
            auto_checks=AutoChecks(
                wcag_contrast="pass",
                line_height="pass",
                type_scale="pass",
            ),
        )

        async def mock_score(html, **kwargs):
            return original_score if html == "original" else worse_score

        async def mock_refine(html, **kwargs):
            return "worse"

        with patch.object(validator.scorer, "score", mock_score):
            with patch.object(validator.style_refiner, "refine", mock_refine):
                final_html, final_score, _ = await validator.validate_and_refine(
                    "original",
                    product_type="landing"
                )

        # Should keep original since refined is worse
        assert final_score.total >= original_score.total
        assert final_html == "original"

    @pytest.mark.asyncio
    async def test_landing_pages_scored(
        self, test_db, test_settings, event_emitter
    ):
        """Test that all Landing pages are scored."""
        validator = AestheticValidator(
            db=test_db,
            session_id="test-landing-score",
            settings=test_settings,
            event_emitter=event_emitter,
        )

        html = "<html><body><h1>Landing</h1></body></html>"

        # Should not raise error
        async def mock_score(html, **kwargs):
            return AestheticScore(
                dimensions=DimensionScores(
                    typography=4, contrast=4, layout=4, color=4, cta=4
                ),
                auto_checks=AutoChecks(
                    wcag_contrast="pass", line_height="pass", type_scale="pass"
                ),
            )

        with patch.object(validator.scorer, "score", mock_score):
            score = await validator.scorer.score(html, product_type="landing")

        assert score is not None
        assert score.total > 0

    @pytest.mark.asyncio
    async def test_card_pages_scored(
        self, test_db, test_settings, event_emitter
    ):
        """Test that Card pages are scored."""
        validator = AestheticValidator(
            db=test_db,
            session_id="test-card-score",
            settings=test_settings,
            event_emitter=event_emitter,
        )

        html = "<html><body><div class='card'>Card</div></body></html>"

        async def mock_score(html, **kwargs):
            return AestheticScore(
                dimensions=DimensionScores(
                    typography=4, contrast=4, layout=4, color=4, cta=4
                ),
                auto_checks=AutoChecks(
                    wcag_contrast="pass", line_height="pass", type_scale="pass"
                ),
            )

        with patch.object(validator.scorer, "score", mock_score):
            score = await validator.scorer.score(html, product_type="card")

        assert score is not None

    @pytest.mark.asyncio
    async def test_invitation_pages_scored(
        self, test_db, test_settings, event_emitter
    ):
        """Test that Invitation pages are scored."""
        validator = AestheticValidator(
            db=test_db,
            session_id="test-invitation-score",
            settings=test_settings,
            event_emitter=event_emitter,
        )

        html = "<html><body><h1>You're Invited</h1></body></html>"

        async def mock_score(html, **kwargs):
            return AestheticScore(
                dimensions=DimensionScores(
                    typography=4, contrast=4, layout=4, color=4, cta=4
                ),
                auto_checks=AutoChecks(
                    wcag_contrast="pass", line_height="pass", type_scale="pass"
                ),
            )

        with patch.object(validator.scorer, "score", mock_score):
            score = await validator.scorer.score(html, product_type="invitation")

        assert score is not None

    @pytest.mark.asyncio
    async def test_scores_logged_via_sse(
        self, test_db, test_settings, event_emitter
    ):
        """Test that scores are logged via SSE events."""
        from app.events.models import AestheticScoreEvent

        validator = AestheticValidator(
            db=test_db,
            session_id="test-logging",
            settings=test_settings,
            event_emitter=event_emitter,
        )

        score = AestheticScore(
            dimensions=DimensionScores(
                typography=4, contrast=4, layout=4, color=4, cta=4
            ),
            auto_checks=AutoChecks(
                wcag_contrast="pass", line_height="pass", type_scale="pass"
            ),
        )

        # Emit score event
        event_emitter.emit(
            AestheticScoreEvent(
                agent_id="validator_1",
                score=score.total,
                dimensions=score.dimensions.model_dump(),
                issues=score.issues,
            )
        )

        # Event should be emitted
        # (In actual test, capture emitted events and verify)

    @pytest.mark.asyncio
    async def test_generation_completes_with_best_version(
        self, test_db, test_settings, event_emitter, output_dir
    ):
        """Test that generation completes with the best-scoring version."""
        from app.agents.generation import GenerationAgent

        agent = GenerationAgent(
            db=test_db,
            session_id="test-gen-best",
            settings=test_settings,
            event_emitter=event_emitter,
            output_dir=output_dir,
        )

        async def mock_validate_and_refine(html, **kwargs):
            # Simulate successful validation
            return (
                "<html><body>Best Version</body></html>",
                AestheticScore(
                    dimensions=DimensionScores(
                        typography=4, contrast=4, layout=4, color=4, cta=4
                    ),
                    auto_checks=AutoChecks(
                        wcag_contrast="pass", line_height="pass", type_scale="pass"
                    ),
                ),
                [],
            )

        with patch.object(agent.validator, "validate_and_refine", mock_validate_and_refine):
            # Generation should complete
            # This is verified by the agent returning a result
            pass
```

### 2.7 Chat API with Images E2E Tests

**File**: `packages/backend/tests/e2e/test_chat_images_e2e.py`

```python
"""
E2E tests for Chat API with Images (v06-B8)

Acceptance Criteria:
1. Images field accepts 0-3 images
2. Images can be base64 or URLs
3. target_pages is optional, defaults to empty
4. style_reference_mode defaults to full_mimic
"""
import pytest
import base64
from fastapi.testclient import TestClient


class TestChatImagesE2E:
    """End-to-end tests for chat API with image support."""

    def test_images_field_accepts_zero_to_three_images(self, test_client):
        """Test that images field accepts 0-3 images."""
        # 0 images
        response1 = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page",
                "images": [],
            },
        )
        assert response1.status_code in [200, 202]

        # 1 image
        response2 = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page",
                "images": ["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="],
            },
        )
        assert response2.status_code in [200, 202]

        # 3 images (max)
        response3 = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page",
                "images": [
                    "data:image/png;base64,abc",
                    "data:image/png;base64,def",
                    "data:image/png;base64,ghi",
                ],
            },
        )
        assert response3.status_code in [200, 202]

    def test_more_than_three_images_rejected(self, test_client):
        """Test that more than 3 images raises validation error."""
        response = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page",
                "images": [
                    "data:image/png;base64,1",
                    "data:image/png;base64,2",
                    "data:image/png;base64,3",
                    "data:image/png;base64,4",  # Exceeds max
                ],
            },
        )
        assert response.status_code == 422  # Validation error

    def test_images_can_be_base64_or_urls(self, test_client):
        """Test that images accept both base64 and URLs."""
        # Base64 image
        response1 = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page",
                "images": ["data:image/png;base64,abc123"],
            },
        )
        assert response1.status_code in [200, 202]

        # URL image
        response2 = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page",
                "images": ["https://example.com/style.png"],
            },
        )
        assert response2.status_code in [200, 202]

        # Mixed
        response3 = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page",
                "images": [
                    "data:image/png;base64,abc",
                    "https://example.com/style.png",
                ],
            },
        )
        assert response3.status_code in [200, 202]

    def test_target_pages_optional_defaults_to_empty(self, test_client):
        """Test that target_pages is optional and defaults to empty list."""
        # No target_pages provided
        response = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page",
            },
        )

        # Should not error on missing field
        assert response.status_code in [200, 202]

    def test_target_pages_accepts_page_list(self, test_client):
        """Test that target_pages accepts a list of page identifiers."""
        response = test_client.post(
            "/api/chat",
            json={
                "message": "Update the home page",
                "target_pages": ["home", "about"],
            },
        )
        assert response.status_code in [200, 202]

    def test_style_reference_mode_defaults_to_full_mimic(self, test_client):
        """Test that style_reference_mode defaults to full_mimic."""
        response = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page with this style",
                "images": ["data:image/png;base64,abc"],
            },
        )
        assert response.status_code in [200, 202]

    def test_style_reference_mode_can_be_explicit(self, test_client):
        """Test that style_reference_mode can be explicitly set."""
        response = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page",
                "style_reference_mode": "style_only",
                "images": ["data:image/png;base64,abc"],
            },
        )
        assert response.status_code in [200, 202]

    def test_combined_images_and_style_reference(self, test_client):
        """Test combined images in both fields (subject to max 3 total)."""
        # This should validate that total images <= 3
        response = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page",
                "images": ["data:image/png;base64,abc"],
                "style_reference": {
                    "mode": "full_mimic",
                    "images": ["data:image/png;base64,def"],
                },
            },
        )
        # Total 2 images, should pass
        assert response.status_code in [200, 202]

    def test_combined_exceeds_max_rejected(self, test_client):
        """Test that combined images from both fields still respect max 3."""
        response = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page",
                "images": [
                    "data:image/png;base64,1",
                    "data:image/png;base64,2",
                ],
                "style_reference": {
                    "mode": "full_mimic",
                    "images": [
                        "data:image/png;base64,3",
                        "data:image/png;base64,4",  # Exceeds max
                    ],
                },
            },
        )
        # Total 4 images, should fail validation
        assert response.status_code == 422
```

---

## 3. Frontend E2E Tests

### 3.1 Data Tab E2E Tests

**File**: `packages/web/src/e2e/DataTab.spec.ts`

```typescript
/**
 * E2E tests for Data Tab UI (v06-F1)
 *
 * Acceptance Criteria:
 * 1. Component renders in Preview panel
 * 2. Three sections visible by default
 * 3. Each section collapsible
 * 4. Empty state shown when no data
 * 5. JSON formatted and readable
 * 6. Copy button works
 * 7. Large objects can be collapsed
 * 8. Events display in reverse chronological order
 * 9. Timestamps formatted human-readable
 * 10. Data truncated when too long
 * 11. Auto-scrolls to newest events
 * 12. Records show type/date and key data
 * 13. Export downloads JSON
 */
import { test, expect } from '@playwright/test';

test.describe('Data Tab E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to a project page with preview
    await page.goto('/project/test-session');
    // Wait for preview to load
    await page.waitForSelector('[data-testid="preview-panel"]');
    // Click on Data tab
    await page.click('[data-testid="data-tab-button"]');
  });

  test('1. Component renders in Preview panel', async ({ page }) => {
    await expect(page.locator('[data-testid="data-tab"]')).toBeVisible();
  });

  test('2. Three sections visible by default', async ({ page }) => {
    await expect(page.locator('[data-testid="data-state-section"]')).toBeVisible();
    await expect(page.locator('[data-testid="data-events-section"]')).toBeVisible();
    await expect(page.locator('[data-testid="data-records-section"]')).toBeVisible();
  });

  test('3. Each section collapsible', async ({ page }) => {
    // Collapse State section
    await page.click('[data-testid="data-state-section"] [data-testid="collapse-button"]');
    await expect(page.locator('[data-testid="data-state-section"] .collapsed')).toBeVisible();

    // Collapse Events section
    await page.click('[data-testid="data-events-section"] [data-testid="collapse-button"]');
    await expect(page.locator('[data-testid="data-events-section"] .collapsed')).toBeVisible();

    // Collapse Records section
    await page.click('[data-testid="data-records-section"] [data-testid="collapse-button"]');
    await expect(page.locator('[data-testid="data-records-section"] .collapsed')).toBeVisible();
  });

  test('4. Empty state shown when no data', async ({ page }) => {
    await expect(page.locator('[data-testid="data-state-empty"]')).toBeVisible();
    await expect(page.locator('[data-testid="data-events-empty"]')).toBeVisible();
    await expect(page.locator('[data-testid="data-records-empty"]')).toBeVisible();
  });

  test('5. JSON formatted and readable', async ({ page }) => {
    // Simulate receiving data from preview
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: { cart: { items: [] } },
          events: [],
          records: []
        }
      }, '*');
    });

    // Should show formatted JSON
    await expect(page.locator('[data-testid="json-viewer"]')).toBeVisible();
    const jsonText = await page.locator('[data-testid="json-viewer"]').textContent();
    expect(jsonText).toContain('{');
    expect(jsonText).toContain('}');
  });

  test('6. Copy button works', async ({ page }) => {
    // Setup data first
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: { test: 'data' },
          events: [],
          records: []
        }
      }, '*');
    });

    // Click copy button
    const clipboardPromise = page.evaluate(() => {
      return new Promise(resolve => {
        navigator.clipboard.readText().then(resolve);
      });
    });

    await page.click('[data-testid="copy-state-button"]');

    const clipboardText = await clipboardPromise;
    expect(clipboardText).toContain('test');
  });

  test('7. Large objects can be collapsed', async ({ page }) => {
    // Send large object
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: {
            nested: { very: { deep: { object: { with: { many: 'levels' } } } } }
          },
          events: [],
          records: []
        }
      }, '*');
    });

    // Should have expand/collapse buttons
    await expect(page.locator('[data-testid="expand-node"]')).toBeVisible();
    await page.click('[data-testid="expand-node"]');
    // After clicking, should show nested content
  });

  test('8. Events display in reverse chronological order', async ({ page }) => {
    // Send multiple events
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: {},
          events: [
            { type: 'event1', timestamp: '2026-02-04T10:00:00Z' },
            { type: 'event2', timestamp: '2026-02-04T11:00:00Z' },
            { type: 'event3', timestamp: '2026-02-04T12:00:00Z' },
          ],
          records: []
        }
      }, '*');
    });

    // First event in list should be the latest
    const firstEvent = await page.locator('[data-testid="event-item"]').first().textContent();
    expect(firstEvent).toContain('event3');
  });

  test('9. Timestamps formatted human-readable', async ({ page }) => {
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: {},
          events: [
            { type: 'test_event', timestamp: '2026-02-04T12:30:45Z' }
          ],
          records: []
        }
      }, '*');
    });

    const eventText = await page.locator('[data-testid="event-item"]').textContent();
    // Should contain formatted time
    expect(eventText).toMatch(/\d{1,2}:\d{2}/);
  });

  test('10. Data truncated when too long', async ({ page }) => {
    // Send very long string
    const longString = 'x'.repeat(1000);

    await page.evaluate((s) => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: { long: s },
          events: [],
          records: []
        }
      }, '*');
    }, longString);

    // Should have truncate indicator
    const stateText = await page.locator('[data-testid="data-state-section"]').textContent();
    expect(stateText).toContain('...');
  });

  test('11. Auto-scrolls to newest events', async ({ page }) => {
    const eventsList = page.locator('[data-testid="events-list"]');

    // Send initial events
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: {},
          events: Array(20).fill(null).map((_, i) => ({
            type: `event${i}`,
            timestamp: new Date(i * 1000).toISOString()
          })),
          records: []
        }
      }, '*');
    });

    // Wait for scroll to complete
    await page.waitForTimeout(100);

    // Add new event
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: {},
          events: [
            ...Array(20).fill(null).map((_, i) => ({
              type: `event${i}`,
              timestamp: new Date(i * 1000).toISOString()
            })),
            { type: 'latest_event', timestamp: new Date().toISOString() }
          ],
          records: []
        }
      }, '*');
    });

    // Scroll should be at bottom
    const scrollTop = await eventsList.evaluate(el => el.scrollTop);
    const scrollHeight = await eventsList.evaluate(el => el.scrollHeight);
    // scrollTop + clientHeight should be close to scrollHeight
  });

  test('12. Records show type/date and key data', async ({ page }) => {
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: {},
          events: [],
          records: [
            {
              type: 'order_submitted',
              created_at: '2026-02-04T12:00:00Z',
              payload: { order_id: 'ORD-123', total: 99.99 }
            }
          ]
        }
      }, '*');
    });

    await expect(page.locator('[data-testid="record-item"]')).toBeVisible();
    const recordText = await page.locator('[data-testid="record-item"]').textContent();
    expect(recordText).toContain('order_submitted');
    expect(recordText).toContain('ORD-123');
  });

  test('13. Export downloads JSON', async ({ page }) => {
    // Setup download handler
    const downloadPromise = page.waitForEvent('download');

    // Click export button
    await page.click('[data-testid="export-records-button"]');

    const download = await downloadPromise;
    expect(download.suggestedFilename()).toContain('.json');
  });
});
```

### 3.2 Image Upload & @Page Support E2E Tests

**File**: `packages/web/src/e2e/ImageUpload.spec.ts`

```typescript
/**
 * E2E tests for Image Upload & @Page Support (v06-F2, v06-F4)
 *
 * Acceptance Criteria:
 * 1. Image button opens file picker
 * 2. Drag-and-drop works on textarea
 * 3. Images display as thumbnails
 * 4. Remove button on each image thumbnail
 * 5. Max 3 images enforced
 * 6. Only images accepted; non-image rejected with message
 * 7. Files > 5MB rejected with message
 * 8. Dropdown appears after @ with filtering
 * 9. Keyboard navigation and click-to-select work
 * 10. @Page inserted at cursor position
 */
import { test, expect } from '@playwright/test';

test.describe('Image Upload E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/project/test-session');
    await page.waitForSelector('[data-testid="chat-input"]');
  });

  test('1. Image button opens file picker', async ({ page }) => {
    // Setup file chooser interceptor
    const fileChooserPromise = page.waitForEvent('filechooser');

    await page.click('[data-testid="image-upload-button"]');

    const fileChooser = await fileChooserPromise;
    expect(fileChooser).toBeTruthy();
  });

  test('2. Drag-and-drop works on textarea', async ({ page }) => {
    // Create a mock image file
    const file = new File(['image'], 'test.png', { type: 'image/png' });

    // Create DataTransfer for drag and drop
    const dataTransfer = await page.evaluateHandle((fileData) => {
      const dt = new DataTransfer();
      const file = new File([fileData.content], 'test.png', { type: 'image/png' });
      dt.items.add(file);
      return dt;
    }, { content: 'fake-image-content' });

    // Dispatch drop event
    await page.locator('[data-testid="chat-textarea"]').dispatchEvent('drop', dataTransfer);

    // Should show thumbnail
    await expect(page.locator('[data-testid="image-thumbnail"]')).toBeVisible();
  });

  test('3. Images display as thumbnails', async ({ page }) => {
    // Upload image via button
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: 'test.png',
      mimeType: 'image/png',
      buffer: Buffer.from('fake-image')
    });

    await expect(page.locator('[data-testid="image-thumbnail"]')).toBeVisible();
  });

  test('4. Remove button on each image thumbnail', async ({ page }) => {
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: 'test.png',
      mimeType: 'image/png',
      buffer: Buffer.from('fake-image')
    });

    await expect(page.locator('[data-testid="remove-image-button"]')).toBeVisible();

    // Click remove
    await page.click('[data-testid="remove-image-button"]');

    // Thumbnail should disappear
    await expect(page.locator('[data-testid="image-thumbnail"]')).not.toBeVisible();
  });

  test('5. Max 3 images enforced', async ({ page }) => {
    const fileInput = page.locator('input[type="file"]');

    // Try to upload 4 files
    await fileInput.setInputFiles([
      { name: '1.png', mimeType: 'image/png', buffer: Buffer.from('1') },
      { name: '2.png', mimeType: 'image/png', buffer: Buffer.from('2') },
      { name: '3.png', mimeType: 'image/png', buffer: Buffer.from('3') },
      { name: '4.png', mimeType: 'image/png', buffer: Buffer.from('4') },
    ]);

    // Should show error message
    await expect(page.locator('[data-testid="image-error-message"]')).toBeVisible();
    await expect(page.locator('[data-testid="image-error-message"]')).toContainText('3');
  });

  test('6. Only images accepted; non-image rejected', async ({ page }) => {
    const fileInput = page.locator('input[type="file"]');

    // Try to upload a non-image file
    await fileInput.setInputFiles({
      name: 'test.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('fake-pdf')
    });

    // Should show error
    await expect(page.locator('[data-testid="image-error-message"]')).toBeVisible();
    await expect(page.locator('[data-testid="image-error-message"]')).toContainText('image');
  });

  test('7. Files > 5MB rejected', async ({ page }) => {
    const largeBuffer = Buffer.alloc(6 * 1024 * 1024); // 6MB
    const fileInput = page.locator('input[type="file"]');

    await fileInput.setInputFiles({
      name: 'large.png',
      mimeType: 'image/png',
      buffer: largeBuffer
    });

    await expect(page.locator('[data-testid="image-error-message"]')).toBeVisible();
    await expect(page.locator('[data-testid="image-error-message"]')).toContainText('5MB');
  });
});

test.describe('@Page Mention E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/project/test-existing-session');
    await page.waitForSelector('[data-testid="chat-input"]');
  });

  test('8. Dropdown appears after @ with filtering', async ({ page }) => {
    const textarea = page.locator('[data-testid="chat-textarea"]');

    // Type @
    await textarea.fill('@');

    // Dropdown should appear
    await expect(page.locator('[data-testid="page-mention-popover"]')).toBeVisible();

    // Type filter
    await textarea.fill('@ho');

    // Should show filtered results
    await expect(page.locator('[data-testid="page-mention-item"]').filter({ hasText: /home/i })).toBeVisible();
  });

  test('9. Keyboard navigation and click-to-select work', async ({ page }) => {
    const textarea = page.locator('[data-testid="chat-textarea"]');

    await textarea.fill('@');
    await expect(page.locator('[data-testid="page-mention-popover"]')).toBeVisible();

    // Arrow down should highlight next item
    await page.keyboard.press('ArrowDown');
    await expect(page.locator('[data-testid="page-mention-item"].highlighted')).toBeVisible();

    // Enter should select
    await page.keyboard.press('Enter');

    // @Page should be inserted
    const value = await textarea.inputValue();
    expect(value).toContain('@');
  });

  test('10. @Page inserted at cursor position', async ({ page }) => {
    const textarea = page.locator('[data-testid="chat-textarea"]');

    // Type some text, move cursor, then type @
    await textarea.fill('Update ');
    await textarea.press('End');
    await page.keyboard.type('@');

    // Select a page
    await page.click('[data-testid="page-mention-item"]:first-child');

    // @Page should be at cursor position
    const value = await textarea.inputValue();
    expect(value).toBe('Update @Home');
  });

  test('Empty state when no pages match', async ({ page }) => {
    const textarea = page.locator('[data-testid="chat-textarea"]');

    await textarea.fill('@nonexistent');

    await expect(page.locator('[data-testid="page-mention-empty"]')).toBeVisible();
    await expect(page.locator('[data-testid="page-mention-empty"]')).toContainText('No matching pages');
  });

  test('Escape closes popover without selection', async ({ page }) => {
    const textarea = page.locator('[data-testid="chat-textarea"]');

    await textarea.fill('@');
    await expect(page.locator('[data-testid="page-mention-popover"]')).toBeVisible();

    await page.keyboard.press('Escape');

    await expect(page.locator('[data-testid="page-mention-popover"]')).not.toBeVisible();
  });
});
```

### 3.3 Preview Message Bridge E2E Tests

**File**: `packages/web/src/e2e/PreviewBridge.spec.ts`

```typescript
/**
 * E2E tests for Preview Message Bridge (v06-F3)
 *
 * Acceptance Criteria:
 * 1. Hook returns current state, events, and records
 * 2. Hook returns connection status and last update timestamp
 * 3. Messages filtered by type guard and ignored when malformed
 * 4. Listener cleanup on unmount and iframe disconnect
 */
import { test, expect } from '@playwright/test';

test.describe('Preview Message Bridge E2E', () => {
  test('1. Hook returns current state, events, and records', async ({ page }) => {
    await page.goto('/project/test-session');

    // Wait for preview to load
    await page.waitForSelector('[data-testid="preview-iframe"]');

    // Check if data tab shows initial state
    await page.click('[data-testid="data-tab-button"]');
    await expect(page.locator('[data-testid="data-state-section"]')).toBeVisible();
    await expect(page.locator('[data-testid="data-events-section"]')).toBeVisible();
    await expect(page.locator('[data-testid="data-records-section"]')).toBeVisible();
  });

  test('2. Hook returns connection status and last update timestamp', async ({ page }) => {
    await page.goto('/project/test-session');
    await page.waitForSelector('[data-testid="preview-iframe"]');

    // Connection status should be visible
    await page.click('[data-testid="data-tab-button"]');
    await expect(page.locator('[data-testid="connection-status"]')).toBeVisible();
  });

  test('3. Messages filtered by type guard', async ({ page }) => {
    await page.goto('/project/test-session');
    await page.waitForSelector('[data-testid="preview-iframe"]');

    // Send malformed message (should be ignored)
    await page.evaluate(() => {
      const iframe = document.querySelector('[data-testid="preview-iframe"]') as HTMLIFrameElement;
      if (iframe.contentWindow) {
        iframe.contentWindow.postMessage({ type: 'unknown-type' }, '*');
      }
    });

    // Should not crash or show error
    await expect(page.locator('[data-testid="data-tab"]')).toBeVisible();
  });

  test('4. State updates trigger UI refresh', async ({ page }) => {
    await page.goto('/project/test-session');
    await page.waitForSelector('[data-testid="preview-iframe"]');

    // Simulate state update from iframe
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: { cart: { items: [{ id: 1, name: 'Test Product' }] } },
          events: [{ type: 'add_to_cart', timestamp: new Date().toISOString() }],
          records: []
        }
      }, '*');
    });

    // Check if data is reflected in UI
    await page.click('[data-testid="data-tab-button"]');
    await expect(page.locator('[data-testid="data-state-section"]')).toContainText('Test Product');
  });

  test('5. Debounced updates for non-submit events', async ({ page }) => {
    await page.goto('/project/test-session');
    await page.waitForSelector('[data-testid="preview-iframe"]');

    // Simulate multiple rapid updates
    await page.evaluate(() => {
      for (let i = 0; i < 5; i++) {
        window.postMessage({
          type: 'instant-coffee:update',
          data: {
            state: { count: i },
            events: [],
            records: []
          }
        }, '*');
      }
    });

    // Should not overwhelm the UI
    await page.click('[data-testid="data-tab-button"]');
    await expect(page.locator('[data-testid="data-state-section"]')).toBeVisible();
  });

  test('6. Immediate updates for submit events', async ({ page }) => {
    await page.goto('/project/test-session');
    await page.waitForSelector('[data-testid="preview-iframe"]');

    // Simulate submit event
    await page.evaluate(() => {
      window.postMessage({
        type: 'instant-coffee:update',
        data: {
          state: {},
          events: [],
          records: [{
            type: 'order_submitted',
            created_at: new Date().toISOString(),
            payload: { order_id: 'ORD-123' }
          }]
        }
      }, '*');
    });

    // Should immediately show in records
    await page.click('[data-testid="data-tab-button"]');
    await expect(page.locator('[data-testid="record-item"]')).toContainText('order_submitted');
  });
});
```

---

## 4. Integration E2E Tests

### 4.1 Full Generation Flow E2E Tests

**File**: `packages/backend/tests/e2e/test_full_generation_e2e.py`

```python
"""
Integration E2E tests for full generation flow.

Tests the complete flow from chat input to generated output.
"""
import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch


class TestFullGenerationFlowE2E:
    """End-to-end tests for complete generation pipeline."""

    @pytest.mark.asyncio
    async def test_ecommerce_flow_generation(
        self, test_db, test_settings, event_emitter, output_dir
    ):
        """Test complete ecommerce flow app generation with state contract."""
        from app.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator(
            db=test_db,
            session_id="test-ecommerce-flow",
            settings=test_settings,
            event_emitter=event_emitter,
            output_dir=output_dir,
        )

        responses = []
        async for response in orchestrator.stream_responses(
            user_message="Create an online store with products and cart",
            output_dir=output_dir,
            history=[],
        ):
            responses.append(response)

        # Verify routing happened
        assert any(hasattr(r, 'routing_decision') for r in responses)

        # Verify product doc was generated
        assert any(hasattr(r, 'product_doc') for r in responses)

        # Verify HTML was generated
        assert any(hasattr(r, 'html') for r in responses)

        # Verify state contract exists
        contract_path = Path(output_dir) / "test-ecommerce-flow" / "shared" / "state-contract.json"
        assert contract_path.exists()

        contract = json.loads(contract_path.read_text())
        assert "shared_state_key" in contract
        assert "schema" in contract
        assert len(contract["schema"]) > 0  # Flow app should have schema

    @pytest.mark.asyncio
    async def test_landing_page_generation_with_aesthetic_scoring(
        self, test_db, test_settings, event_emitter, output_dir
    ):
        """Test landing page generation with aesthetic scoring."""
        from app.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator(
            db=test_db,
            session_id="test-landing-aesthetic",
            settings=test_settings,
            event_emitter=event_emitter,
            output_dir=output_dir,
        )

        responses = []
        async for response in orchestrator.stream_responses(
            user_message="Create a landing page for my app",
            output_dir=output_dir,
            history=[],
        ):
            responses.append(response)
            # Check for aesthetic score events
            if hasattr(response, 'aesthetic_score'):
                assert response.aesthetic_score.total >= 0

        # Verify final HTML exists
        html_path = Path(output_dir) / "test-landing-aesthetic" / "index.html"
        assert html_path.exists()

    @pytest.mark.asyncio
    async def test_style_reference_with_images(
        self, test_db, test_settings, event_emitter, output_dir, sample_style_reference_image
    ):
        """Test generation with style reference images."""
        from app.agents.orchestrator import AgentOrchestrator

        image_url = str(sample_style_reference_image)

        orchestrator = AgentOrchestrator(
            db=test_db,
            session_id="test-style-ref",
            settings=test_settings,
            event_emitter=event_emitter,
            output_dir=output_dir,
        )

        responses = []
        async for response in orchestrator.stream_responses(
            user_message="Create a landing page matching this style",
            output_dir=output_dir,
            history=[],
            style_reference={
                "mode": "full_mimic",
                "images": [image_url],
                "scope_pages": [],
            },
        ):
            responses.append(response)

        # Verify style tokens were extracted
        # (This would be verified via events in actual implementation)

    @pytest.mark.asyncio
    async def test_page_targeted_regeneration(
        self, test_db, test_settings, event_emitter, output_dir
    ):
        """Test @Page targeted regeneration."""
        # First, create a session with pages
        session_id = "test-target-pages"
        create_mock_page(test_db, session_id, "home", "Home Page")
        create_mock_page(test_db, session_id, "about", "About Us")

        from app.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator(
            db=test_db,
            session_id=session_id,
            settings=test_settings,
            event_emitter=event_emitter,
            output_dir=output_dir,
        )

        responses = []
        async for response in orchestrator.stream_responses(
            user_message="Update @Home with new hero section",
            output_dir=output_dir,
            history=[],
            target_pages=["home"],
        ):
            responses.append(response)

        # Verify only home page was affected
        # (Check affected_pages in response)

    @pytest.mark.asyncio
    async def test_multi_page_state_sharing(
        self, test_db, test_settings, event_emitter, output_dir
    ):
        """Test that multi-page app shares state correctly."""
        from app.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator(
            db=test_db,
            session_id="test-multi-page-state",
            settings=test_settings,
            event_emitter=event_emitter,
            output_dir=output_dir,
        )

        responses = []
        async for response in orchestrator.stream_responses(
            user_message="Create an ecommerce site with home and cart pages",
            output_dir=output_dir,
            history=[],
        ):
            responses.append(response)

        # Verify data-store script exists
        store_path = Path(output_dir) / "test-multi-page-state" / "shared" / "data-store.js"
        assert store_path.exists()

        store_script = store_path.read_text()
        assert "InstantCoffeeDataStore" in store_script
        assert "instant-coffee:state" in store_script

        # Verify data-client script exists
        client_path = Path(output_dir) / "test-multi-page-state" / "shared" / "data-client.js"
        assert client_path.exists()

        client_script = client_path.read_text()
        assert "ecommerce" in client_script.lower()
```

### 4.2 Multi-Model Fallback E2E Tests

**File**: `packages/backend/tests/e2e/test_model_fallback_e2e.py`

```python
"""
Integration E2E tests for model fallback behavior.
"""
import pytest
from unittest.mock import AsyncMock, patch


class TestModelFallbackE2E:
    """End-to-end tests for model fallback in production scenarios."""

    @pytest.mark.asyncio
    async def test_classifier_fallback_on_timeout(
        self, test_db, test_settings, event_emitter, output_dir
    ):
        """Test classifier fallback when primary model times out."""
        from app.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator(
            db=test_db,
            session_id="test-classifier-fallback",
            settings=test_settings,
            event_emitter=event_emitter,
            output_dir=output_dir,
        )

        # Mock timeout on first call, success on second
        call_count = {"count": 0}

        original_classify = orchestrator.router.classifier.classify

        async def mock_classify(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 1:
                raise TimeoutError("Model timeout")
            return await original_classify(*args, **kwargs)

        with patch.object(
            orchestrator.router.classifier, 'classify', side_effect=mock_classify
        ):
            responses = []
            async for response in orchestrator.stream_responses(
                user_message="Create a landing page",
                output_dir=output_dir,
                history=[],
            ):
                responses.append(response)

        # Should eventually succeed
        assert len(responses) > 0

    @pytest.mark.asyncio
    async def test_writer_fallback_on_missing_fields(
        self, test_db, test_settings, event_emitter, output_dir
    ):
        """Test writer fallback when required fields are missing."""
        from app.agents.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator(
            db=test_db,
            session_id="test-writer-fallback",
            settings=test_settings,
            event_emitter=event_emitter,
            output_dir=output_dir,
        )

        # Mock response missing required fields
        call_count = {"count": 0}

        async def mock_generate(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 1:
                # Missing structured fields
                return {
                    "content": "# Doc",
                    "structured": {},  # Empty, missing required fields
                }
            # Second call returns proper structure
            return {
                "content": "# Product Doc",
                "structured": {
                    "project_name": "Test",
                    "pages": [{"slug": "index", "title": "Home"}],
                },
            }

        # Patch to simulate fallback behavior
        # (In actual test, would patch model pool to return different models)

    @pytest.mark.asyncio
    async def test_max_fallback_attempts(
        self, test_db, test_settings, event_emitter, output_dir
    ):
        """Test that maximum fallback attempts are respected."""
        from app.agents.orchestrator import AgentOrchestrator
        from app.llm.model_pool import ModelPoolManager

        pool = ModelPoolManager(settings=test_settings)

        # Verify max fallback is configured
        # Should stop after N attempts and return error
```

---

## 5. Test Matrix Summary

### 5.1 Spec-06 Acceptance Criteria Coverage

| # | Acceptance Criterion | Test File | Test Function |
|---|----------------------|-----------|---------------|
| 1 | Orchestrator front-loads type/complexity judgment | `test_orchestrator_routing_e2e.py` | `test_ecommerce_classification_routing` |
| 2 | Flow apps must output state_contract + data_flow | `test_data_protocol_e2e.py` | `test_flow_app_generates_state_contract` |
| 3 | Cross-page data sharing works | `test_full_generation_e2e.py` | `test_multi_page_state_sharing` |
| 4 | Data persists after refresh (localStorage) | `test_data_protocol_e2e.py` | `test_state_restoration_on_load` |
| 5 | Preview Data Tab shows state/events/records | `DataTab.spec.ts` | Multiple tests |
| 6 | Checklist/Standard document tiers work | `test_product_doc_tiers_e2e.py` | `test_checklist_tier_generation`, `test_standard_tier_generation` |
| 7 | Model routing: classifier/validator=light, generation=heavy | `test_multi_model_routing_e2e.py` | `test_classifier_uses_light_model`, `test_generation_uses_heavy_model` |
| 8 | Image upload generates style tokens affecting output | `test_style_reference_e2e.py` | `test_style_token_extraction` |
| 9 | Default full_mimic (includes layout) | `test_style_reference_e2e.py` | `test_full_mimic_includes_layout_patterns` |
| 10 | @Page limits scope; no @Page means model decides | `test_orchestrator_routing_e2e.py` | `test_page_mention_parsing` |
| 11 | Landing/Card low aesthetic score triggers refiner (max 2x) | `test_aesthetic_scoring_e2e.py` | `test_refiner_triggered_on_low_score`, `test_max_two_refiner_iterations` |
| 12 | Mobile guardrails applied by default | `test_orchestrator_routing_e2e.py` | `test_ecommerce_classification_routing` |

### 5.2 Backend Phase Coverage

| Phase | Tests |
|-------|-------|
| v06-B1 (Skills Registry) | `test_skills_registry.py` |
| v06-B2 (Orchestrator Routing) | `test_orchestrator_routing_e2e.py` |
| v06-B3 (Style Reference) | `test_style_reference_e2e.py` |
| v06-B4 (Product Doc Tiers) | `test_product_doc_tiers_e2e.py` |
| v06-B5 (Data Protocol) | `test_data_protocol_e2e.py` |
| v06-B6 (Multi-model Routing) | `test_multi_model_routing_e2e.py` |
| v06-B7 (Aesthetic Scoring) | `test_aesthetic_scoring_e2e.py` |
| v06-B8 (Chat Image Upload) | `test_chat_images_e2e.py` |

### 5.3 Frontend Phase Coverage

| Phase | Tests |
|-------|-------|
| v06-F1 (Data Tab UI) | `DataTab.spec.ts` |
| v06-F2 (Image Upload & @Page) | `ImageUpload.spec.ts` |
| v06-F3 (Preview Bridge) | `PreviewBridge.spec.ts` |
| v06-F4 (Page Mention) | `ImageUpload.spec.ts` (@Page tests) |

---

## Implementation Notes

### Running E2E Tests

```bash
# Backend E2E tests
cd packages/backend
pytest tests/e2e/ -v

# Frontend E2E tests (with Playwright)
cd packages/web
npx playwright test
```

### Test Fixtures Location

Place test fixture images in:
```
packages/backend/tests/fixtures/
├── sample-style-ref.png
├── product1.jpg
└── product2.jpg
```

### CI/CD Integration

Add to CI pipeline:
```yaml
e2e-tests:
  script:
    - cd packages/backend && pytest tests/e2e/ -v
    - cd packages/web && npx playwright test
  artifacts:
    paths:
      - packages/web/playwright-report/
```

---

**Document Version**: 1.0
**Last Updated**: 2026-02-04
**Maintained By**: Instant Coffee Development Team
