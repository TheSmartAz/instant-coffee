import asyncio

from app.graph.nodes.component_registry import component_registry_node
from app.graph.nodes.generate import generate_node
from app.schemas.component import normalize_design_tokens
from app.services.component_validator import auto_fix_unknown_components, validate_page_schema


def test_normalize_design_tokens_maps_full_radius() -> None:
    tokens = normalize_design_tokens(
        {"radius": "full", "spacing": "airy", "shadow": "strong"}
    )
    assert tokens.radius == "large"
    assert tokens.spacing == "airy"
    assert tokens.shadow == "strong"


def test_component_registry_node_outputs_default_registry() -> None:
    state = {"style_tokens": {"radius": "small", "spacing": "compact", "shadow": "subtle"}}
    result = asyncio.run(component_registry_node(state))
    registry = result.get("component_registry")
    assert isinstance(registry, dict)
    assert isinstance(registry.get("components"), list)
    assert len(registry.get("components")) >= 20
    tokens = registry.get("tokens")
    assert isinstance(tokens, dict)
    assert tokens.get("radius") == "small"
    assert isinstance(result.get("component_registry_hash"), str)

    second = asyncio.run(component_registry_node(result))
    assert second.get("component_registry_hash") == result.get("component_registry_hash")


def test_component_validator_detects_and_fixes_unknown() -> None:
    registry = {
        "components": [
            {"id": "nav-primary"},
            {"id": "footer-simple"},
        ]
    }
    schema = {
        "slug": "index",
        "title": "Home",
        "layout": "default",
        "components": [
            {"id": "navprimary", "key": "nav-1", "props": {}},
            {"id": "footer-simple", "key": "footer-1", "props": {}},
        ],
    }
    errors = validate_page_schema(schema, registry)
    assert errors
    fixed = auto_fix_unknown_components(schema, registry)
    errors = validate_page_schema(fixed, registry)
    assert errors == []
    assert fixed["components"][0]["id"] == "nav-primary"


def test_generate_node_builds_schema_with_registry() -> None:
    registry = asyncio.run(component_registry_node({})).get("component_registry")
    state = {
        "component_registry": registry,
        "pages": [{"slug": "index", "title": "Home", "role": "landing"}],
    }
    result = asyncio.run(generate_node(state))
    schemas = result.get("page_schemas")
    assert isinstance(schemas, list)
    assert schemas
    for schema in schemas:
        assert validate_page_schema(schema, registry) == []
