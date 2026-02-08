from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional


_SKILLS_ROOT = Path(__file__).resolve().parent
_MANIFESTS_DIR = _SKILLS_ROOT / "manifests"
_RULES_DIR = _SKILLS_ROOT / "rules"
_CONTRACTS_DIR = _SKILLS_ROOT / "contracts"
_ENV_MANIFESTS_DIR = "SKILLS_MANIFEST_DIR"
_ENV_SKILLS_DIR = "SKILLS_DIR"

_VALID_PRODUCT_TYPES = {
    "ecommerce",
    "travel",
    "manual",
    "kanban",
    "booking",
    "dashboard",
    "landing",
    "card",
    "invitation",
}
_VALID_DOC_TIERS = {"checklist", "standard", "extended"}
_MODEL_PREF_KEYS = {"classifier", "writer", "validator", "expander", "style_refiner"}


class SkillRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelPreference:
    classifier: str = "light"
    writer: str = "heavy"
    validator: str = "light"
    expander: str = "mid"
    style_refiner: str = "mid"

    @classmethod
    def from_payload(cls, payload: Optional[dict]) -> "ModelPreference":
        if not payload:
            return cls()
        unknown = set(payload.keys()) - _MODEL_PREF_KEYS
        if unknown:
            raise SkillRegistryError(f"Unknown model_prefs keys: {sorted(unknown)}")
        values = {key: str(value) for key, value in payload.items() if key in _MODEL_PREF_KEYS}
        return cls(**values)

    def to_dict(self) -> Dict[str, str]:
        return {
            "classifier": self.classifier,
            "writer": self.writer,
            "validator": self.validator,
            "expander": self.expander,
            "style_refiner": self.style_refiner,
        }


@dataclass(frozen=True)
class SkillManifest:
    id: str
    name: str
    version: str
    product_types: List[str]
    doc_tiers: List[str]
    components: List[str] = field(default_factory=list)
    state_contract: Optional[str] = None
    style_profiles: List[str] = field(default_factory=list)
    guardrails: Optional[str] = None
    model_prefs: ModelPreference = field(default_factory=ModelPreference)
    page_roles: List[str] = field(default_factory=list)
    priority: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_manifest(self)


@dataclass(frozen=True)
class StyleProfile:
    id: str
    name: str
    description: str
    tokens: Dict[str, Any]


@dataclass(frozen=True)
class GuardrailRule:
    id: str
    title: str
    description: str
    category: str
    priority: str


@dataclass(frozen=True)
class Guardrails:
    hard: List[GuardrailRule]
    soft: List[GuardrailRule]


class SkillsRegistry:
    def __init__(
        self,
        manifests_dir: Optional[Path | str] = None,
        contracts_dir: Optional[Path | str] = None,
        rules_dir: Optional[Path | str] = None,
        enable_reload: bool = False,
    ) -> None:
        self._manifests: Dict[str, SkillManifest] = {}
        self._manifest_paths: Dict[str, Path] = {}
        self._loaded = False
        self._enable_reload = enable_reload
        self._manifests_dir = _resolve_manifests_dir(manifests_dir)
        self._skills_root = self._manifests_dir.parent
        self._contracts_dir = Path(contracts_dir) if contracts_dir else _CONTRACTS_DIR
        self._rules_dir = Path(rules_dir) if rules_dir else _RULES_DIR

    def load(self) -> None:
        self.load_manifests()

    def load_manifests(self, directory: Optional[Path | str] = None, force: bool = False) -> None:
        if self._loaded and not (force or self._enable_reload or directory):
            return
        manifests_dir = Path(directory) if directory else self._manifests_dir
        if not manifests_dir.exists():
            raise SkillRegistryError(f"Missing manifests directory: {manifests_dir}")
        manifests: Dict[str, SkillManifest] = {}
        manifest_paths: Dict[str, Path] = {}
        for path in sorted(manifests_dir.glob("*.json")):
            payload = _load_json(path)
            manifest = _parse_manifest(payload)
            manifests[manifest.id] = manifest
            manifest_paths[manifest.id] = path
        self._manifests = manifests
        self._manifest_paths = manifest_paths
        self._loaded = True

    def list(self) -> List[SkillManifest]:
        self.load()
        return list(self._manifests.values())

    def list_all_skills(self) -> List[SkillManifest]:
        return self.list()

    def get(self, skill_id: str) -> Optional[SkillManifest]:
        self.load()
        return self._manifests.get(skill_id)

    def get_skill(self, skill_id: str) -> Optional[SkillManifest]:
        return self.get(skill_id)

    def select_by_product(self, product_type: str) -> List[SkillManifest]:
        self.load()
        product_type = product_type.lower().strip()
        matches = [
            manifest
            for manifest in self._manifests.values()
            if product_type in [item.lower() for item in manifest.product_types]
        ]
        return sorted(matches, key=lambda m: m.priority, reverse=True)

    def find_skills(self, product_type: str, complexity: Optional[str] = None) -> List[SkillManifest]:
        matches = self.select_by_product(product_type)
        if not complexity:
            return matches
        complexity = complexity.lower().strip()
        filtered: List[SkillManifest] = []
        for manifest in matches:
            tiers = [tier.lower() for tier in manifest.doc_tiers]
            extra_levels = _coerce_str_list(manifest.extra.get("complexity"))
            extra_levels.extend(_coerce_str_list(manifest.extra.get("complexities")))
            levels = set(tiers + extra_levels)
            if not levels or complexity in levels:
                filtered.append(manifest)
        return sorted(filtered, key=lambda m: m.priority, reverse=True)

    def select_best(self, product_type: str) -> Optional[SkillManifest]:
        matches = self.select_by_product(product_type)
        return matches[0] if matches else None

    def get_state_contract(self, skill_id: str) -> Optional[dict]:
        manifest = self.get(skill_id)
        if not manifest or not manifest.state_contract:
            return None
        manifest_path = self._manifest_paths.get(manifest.id)
        contract_path = resolve_contract_path(
            manifest.state_contract,
            base_dir=manifest_path,
            contracts_dir=self._contracts_dir,
            skills_root=self._skills_root,
        )
        if not contract_path:
            return None
        try:
            return _load_json(contract_path)
        except SkillRegistryError:
            return None

    def get_guardrails(self, skill_id: str) -> Optional[Guardrails]:
        manifest = self.get(skill_id)
        if not manifest:
            return None
        try:
            return load_guardrails(
                manifest.guardrails,
                base_dir=self._manifest_paths.get(skill_id),
                rules_dir=self._rules_dir,
                skills_root=self._skills_root,
            )
        except SkillRegistryError:
            return None

    def load_style_profiles(self) -> Dict[str, StyleProfile]:
        return load_style_profiles(self._rules_dir)

    def load_guardrails(self) -> Guardrails:
        return load_guardrails(None, rules_dir=self._rules_dir, skills_root=self._skills_root)


class SkillRegistry(SkillsRegistry):
    pass


def load_style_profiles(rules_dir: Optional[Path] = None) -> Dict[str, StyleProfile]:
    rules_dir = rules_dir or _RULES_DIR
    path = rules_dir / "style-profiles.json"
    payload = _load_json(path)
    profiles: Dict[str, StyleProfile] = {}
    for profile_id, data in payload.get("profiles", {}).items():
        profiles[profile_id] = StyleProfile(
            id=profile_id,
            name=str(data.get("name", profile_id)),
            description=str(data.get("description", "")),
            tokens=dict(data.get("tokens", {})),
        )
    return profiles


def load_style_router(rules_dir: Optional[Path] = None) -> dict:
    rules_dir = rules_dir or _RULES_DIR
    path = rules_dir / "style-router.json"
    return _load_json(path)


def route_style_profile(user_text: str, router: Optional[dict] = None) -> str:
    if not user_text:
        router = router or load_style_router()
        return str(router.get("default_profile", "clean-modern"))
    router = router or load_style_router()
    text = user_text.lower()
    for rule in router.get("rules", []):
        keywords = [str(k).lower() for k in rule.get("keywords", [])]
        for keyword in keywords:
            if _keyword_match(text, keyword):
                return str(rule.get("profile"))
    return str(router.get("default_profile", "clean-modern"))


def load_guardrails(
    guardrails_ref: Optional[str] = None,
    base_dir: Optional[Path] = None,
    rules_dir: Optional[Path] = None,
    skills_root: Optional[Path] = None,
) -> Guardrails:
    rules_dir = rules_dir or _RULES_DIR
    path = resolve_guardrails_path(
        guardrails_ref,
        base_dir=base_dir,
        rules_dir=rules_dir,
        skills_root=skills_root,
    )
    if not path:
        raise SkillRegistryError("Missing guardrails file reference.")
    payload = _load_json(path)
    hard = [_parse_guardrail_rule(item) for item in payload.get("hard", [])]
    soft = [_parse_guardrail_rule(item) for item in payload.get("soft", [])]
    return Guardrails(hard=hard, soft=soft)


def resolve_contract_path(
    contract_ref: Optional[str],
    base_dir: Optional[Path] = None,
    contracts_dir: Optional[Path] = None,
    skills_root: Optional[Path] = None,
) -> Optional[Path]:
    if not contract_ref:
        return None
    contracts_dir = contracts_dir or _CONTRACTS_DIR
    base_dirs = _collect_base_dirs(base_dir, skills_root)
    return _resolve_relative_path(contract_ref, base_dirs, [contracts_dir])


def resolve_guardrails_path(
    guardrails_ref: Optional[str],
    base_dir: Optional[Path] = None,
    rules_dir: Optional[Path] = None,
    skills_root: Optional[Path] = None,
) -> Optional[Path]:
    rules_dir = rules_dir or _RULES_DIR
    base_dirs = _collect_base_dirs(base_dir, skills_root)
    if guardrails_ref:
        return _resolve_relative_path(guardrails_ref, base_dirs, [rules_dir])
    default_path = rules_dir / "mobile-guardrails.json"
    return default_path if default_path.exists() else None


def _parse_manifest(payload: dict) -> SkillManifest:
    known_keys = {
        "id",
        "name",
        "version",
        "product_types",
        "doc_tiers",
        "components",
        "state_contract",
        "style_profiles",
        "guardrails",
        "model_prefs",
        "page_roles",
        "priority",
    }
    extra = {key: value for key, value in payload.items() if key not in known_keys}
    return SkillManifest(
        id=str(payload.get("id", "")),
        name=str(payload.get("name", "")),
        version=str(payload.get("version", "")),
        product_types=list(payload.get("product_types", [])),
        doc_tiers=list(payload.get("doc_tiers", [])),
        components=list(payload.get("components", [])),
        state_contract=payload.get("state_contract"),
        style_profiles=list(payload.get("style_profiles", [])),
        guardrails=payload.get("guardrails"),
        model_prefs=ModelPreference.from_payload(payload.get("model_prefs")),
        page_roles=list(payload.get("page_roles", [])),
        priority=int(payload.get("priority", 0)),
        extra=extra,
    )


def _parse_guardrail_rule(payload: dict) -> GuardrailRule:
    return GuardrailRule(
        id=str(payload.get("id", "")),
        title=str(payload.get("title", "")),
        description=str(payload.get("description", "")),
        category=str(payload.get("category", "")),
        priority=str(payload.get("priority", "")),
    )


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise SkillRegistryError(f"Missing skill file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _keyword_match(text: str, keyword: str) -> bool:
    if not keyword:
        return False
    if re.match(r"^[a-z0-9]+$", keyword):
        return re.search(rf"\\b{re.escape(keyword)}\\b", text) is not None
    return keyword in text


def _resolve_manifests_dir(manifests_dir: Optional[Path | str]) -> Path:
    if manifests_dir:
        return Path(manifests_dir)
    env_value = os.getenv(_ENV_MANIFESTS_DIR) or os.getenv(_ENV_SKILLS_DIR)
    if env_value:
        return Path(env_value).expanduser()
    return _MANIFESTS_DIR


def _resolve_relative_path(
    path_ref: str,
    base_dirs: Iterable[Path],
    fallback_dirs: Iterable[Path],
) -> Optional[Path]:
    candidate = Path(path_ref)
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    for base_dir in base_dirs:
        base_candidate = base_dir / path_ref
        if base_candidate.exists():
            return base_candidate
    for fallback_dir in fallback_dirs:
        fallback_candidate = fallback_dir / path_ref
        if fallback_candidate.exists():
            return fallback_candidate
    return None


def _collect_base_dirs(base_dir: Optional[Path], skills_root: Optional[Path]) -> List[Path]:
    bases: List[Path] = []
    if base_dir:
        base_dir = base_dir.parent if base_dir.is_file() else base_dir
        bases.append(base_dir)
        if base_dir.parent != base_dir:
            bases.append(base_dir.parent)
    if skills_root and skills_root not in bases:
        bases.append(skills_root)
    if _SKILLS_ROOT not in bases:
        bases.append(_SKILLS_ROOT)
    return bases


def _validate_manifest(manifest: SkillManifest) -> None:
    if not manifest.id or not manifest.name or not manifest.version:
        raise SkillRegistryError("SkillManifest requires id, name, and version.")
    if not manifest.product_types:
        raise SkillRegistryError("SkillManifest requires at least one product_type.")
    invalid_product_types = {
        product_type for product_type in manifest.product_types if product_type not in _VALID_PRODUCT_TYPES
    }
    if invalid_product_types:
        raise SkillRegistryError(f"Invalid product_types: {sorted(invalid_product_types)}")
    invalid_doc_tiers = {tier for tier in manifest.doc_tiers if tier not in _VALID_DOC_TIERS}
    if invalid_doc_tiers:
        raise SkillRegistryError(f"Invalid doc_tiers: {sorted(invalid_doc_tiers)}")


def _coerce_str_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value.lower()]
    if isinstance(value, Iterable):
        return [str(item).lower() for item in value if item is not None]
    return [str(value).lower()]


__all__ = [
    "ModelPreference",
    "SkillManifest",
    "SkillsRegistry",
    "SkillRegistry",
    "StyleProfile",
    "GuardrailRule",
    "Guardrails",
    "load_guardrails",
    "load_style_profiles",
    "load_style_router",
    "route_style_profile",
    "resolve_contract_path",
    "resolve_guardrails_path",
]
