import pytest

from app.services.skills import (
    SkillRegistryError,
    SkillsRegistry,
    _parse_manifest,
)


def test_manifest_validation_requires_fields() -> None:
    payload = {
        "name": "Missing ID",
        "version": "1.0.0",
        "product_types": ["landing"],
        "doc_tiers": ["standard"],
    }
    with pytest.raises(SkillRegistryError):
        _parse_manifest(payload)


def test_manifest_validation_rejects_invalid_product_type() -> None:
    payload = {
        "id": "bad-skill",
        "name": "Bad",
        "version": "1.0.0",
        "product_types": ["unknown"],
        "doc_tiers": ["standard"],
    }
    with pytest.raises(SkillRegistryError):
        _parse_manifest(payload)


def test_manifest_validation_rejects_unknown_model_prefs() -> None:
    payload = {
        "id": "bad-skill",
        "name": "Bad",
        "version": "1.0.0",
        "product_types": ["landing"],
        "doc_tiers": ["standard"],
        "model_prefs": {"writer": "heavy", "unknown": "oops"},
    }
    with pytest.raises(SkillRegistryError):
        _parse_manifest(payload)


def test_registry_loads_manifests() -> None:
    registry = SkillsRegistry()
    skills = registry.list_all_skills()
    ids = {skill.id for skill in skills}
    assert "flow-ecommerce-v1" in ids
    assert "static-landing-v1" in ids


def test_registry_get_state_contract() -> None:
    registry = SkillsRegistry()
    contract = registry.get_state_contract("flow-ecommerce-v1")
    assert contract is not None
    assert contract.get("shared_state_key") == "instant-coffee:state"


def test_find_skills_filters_by_complexity() -> None:
    registry = SkillsRegistry()
    matches = registry.find_skills("landing", "standard")
    assert any(skill.id == "static-landing-v1" for skill in matches)
    empty = registry.find_skills("landing", "extended")
    assert empty == []
