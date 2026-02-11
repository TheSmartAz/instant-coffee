from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional


def slugify_component_id(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "")).strip("-").lower()
    if not text:
        return "component"
    return text[:50]


class ComponentRegistryService:
    def __init__(self, output_dir: str, session_id: str) -> None:
        base = Path(output_dir).expanduser().resolve()
        self._session_dir = base / session_id
        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._components_dir = self._session_dir / "components"

    @property
    def session_dir(self) -> Path:
        return self._session_dir

    @property
    def components_dir(self) -> Path:
        return self._components_dir

    def ensure_components_dir(self) -> Path:
        self._components_dir.mkdir(parents=True, exist_ok=True)
        return self._components_dir

    def registry_path(self) -> Path:
        return self.ensure_components_dir() / "components.json"

    def write_component(self, filename: str, html: str) -> Path:
        self.ensure_components_dir()
        safe_name = filename.strip().lstrip("/").replace("\\", "/")
        path = self._components_dir / safe_name
        path.write_text(html or "", encoding="utf-8")
        return path

    def write_registry(self, registry: Dict[str, Any]) -> Path:
        path = self.registry_path()
        path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def read_registry(self) -> Optional[Dict[str, Any]]:
        path = self.registry_path()
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def compute_hash(self, payload: Dict[str, Any]) -> str:
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return "sha256:" + hashlib.sha256(normalized).hexdigest()

    def resolve_relative_path(self, relative_path: str) -> Path:
        cleaned = (relative_path or "").lstrip("/").replace("\\", "/")
        return self._session_dir / cleaned


__all__ = ["ComponentRegistryService", "slugify_component_id"]
