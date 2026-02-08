from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable

from ..schemas.asset import AssetRegistry, AssetRef
from ..services.asset_registry import AssetRegistryService

logger = logging.getLogger(__name__)


class SchemaFileGenerator:
    def __init__(
        self,
        project_root: Path | str,
        *,
        session_id: str | None = None,
        assets_base_dir: Path | None = None,
    ) -> None:
        self.project_root = Path(project_root)
        self.session_id = session_id
        self.assets_base_dir = assets_base_dir
        self.data_dir = self.project_root / "src" / "data"
        self.pages_dir = self.project_root / "src" / "pages"
        self.public_assets_dir = self.project_root / "public" / "assets"

    def generate(
        self,
        page_schemas: Iterable[dict[str, Any]] | None,
        component_registry: dict[str, Any] | None,
        style_tokens: dict[str, Any] | None,
        assets: Any,
    ) -> dict[str, Any]:
        schemas = list(page_schemas or [])
        registry_payload = component_registry or {}
        tokens_payload = style_tokens or {}

        asset_registry = self._normalize_asset_registry(assets)
        asset_registry = self._copy_assets(asset_registry, assets)

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(self.data_dir / "schemas.json", schemas)
        self._write_json(self.data_dir / "tokens.json", tokens_payload)
        self._write_json(self.data_dir / "registry.json", registry_payload)
        self._write_json(self.data_dir / "assets.json", asset_registry)

        self._write_page_components(schemas)

        return asset_registry

    def _write_page_components(self, page_schemas: Iterable[dict[str, Any]]) -> None:
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self._clear_generated_pages()

        for schema in page_schemas:
            slug = self._normalize_slug((schema or {}).get("slug"))
            filename = self._safe_filename(slug)
            target = self.pages_dir / f"{filename}.tsx"
            if filename == "index":
                target = self.pages_dir / "index.tsx"
            target.write_text(self._page_component_source(slug), encoding="utf-8")

    def _clear_generated_pages(self) -> None:
        if not self.pages_dir.exists():
            return
        for path in sorted(self.pages_dir.rglob("*.tsx")):
            if path.name == "_template.tsx":
                continue
            try:
                path.unlink()
            except OSError:
                logger.warning("Failed to remove stale page component: %s", path)
        for path in sorted(self.pages_dir.rglob("*"), reverse=True):
            if path.is_dir() and path != self.pages_dir:
                try:
                    path.rmdir()
                except OSError:
                    continue

    def _page_component_source(self, slug: str) -> str:
        return "\n".join(
            [
                "import { createPage } from './_template'",
                "",
                f"export default createPage('{slug}')",
                "",
            ]
        )

    def _normalize_asset_registry(self, assets: Any) -> dict[str, Any]:
        registry = self._empty_registry()

        payload = None
        if isinstance(assets, AssetRegistry):
            payload = assets.model_dump()
        elif isinstance(assets, dict):
            has_registry_keys = any(
                key in assets
                for key in (
                    "logo",
                    "style_refs",
                    "styleRefs",
                    "backgrounds",
                    "product_images",
                    "productImages",
                )
            )
            if has_registry_keys:
                payload = {
                    "logo": assets.get("logo"),
                    "style_refs": assets.get("style_refs") or assets.get("styleRefs") or [],
                    "backgrounds": assets.get("backgrounds") or [],
                    "product_images": assets.get("product_images")
                    or assets.get("productImages")
                    or [],
                }
        elif isinstance(assets, list):
            payload = {"style_refs": assets}

        if payload:
            registry = self._merge_registry(registry, self._normalize_registry_payload(payload))

        service_registry = self._load_registry_from_service()
        if service_registry:
            registry = self._merge_registry(service_registry, registry)

        if isinstance(assets, dict) and assets.get("files"):
            registry = self._merge_registry(registry, self._registry_from_files(assets.get("files") or []))

        return registry

    def _load_registry_from_service(self) -> dict[str, Any] | None:
        if not self.session_id:
            return None
        try:
            service = AssetRegistryService(self.session_id, base_dir=self._assets_base_path())
            return service.get_registry().model_dump()
        except Exception:
            logger.debug("Asset registry unavailable for session %s", self.session_id)
            return None

    def _assets_base_path(self) -> Path:
        if self.assets_base_dir is not None:
            return Path(self.assets_base_dir)
        return Path("~/.instant-coffee/sessions").expanduser()

    def _registry_from_files(self, files: Iterable[dict[str, Any]]) -> dict[str, Any]:
        entries = []
        for item in files:
            if not isinstance(item, dict):
                continue
            filename = item.get("filename") or item.get("name")
            if not filename and item.get("path"):
                filename = Path(str(item.get("path"))).name
            if not filename:
                continue
            entry = {
                "id": item.get("id") or f"asset:{Path(filename).stem}",
                "url": f"/assets/{filename}",
            }
            if item.get("type"):
                entry["type"] = item.get("type")
            if item.get("width"):
                entry["width"] = item.get("width")
            if item.get("height"):
                entry["height"] = item.get("height")
            entry["path"] = item.get("path")
            entry["filename"] = filename
            entries.append(entry)

        return {
            "logo": None,
            "style_refs": [],
            "backgrounds": [],
            "product_images": entries,
        }

    def _normalize_registry_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "logo": self._normalize_asset_entry(payload.get("logo")),
            "style_refs": self._normalize_asset_list(payload.get("style_refs") or []),
            "backgrounds": self._normalize_asset_list(payload.get("backgrounds") or []),
            "product_images": self._normalize_asset_list(payload.get("product_images") or []),
        }

    def _normalize_asset_entry(self, entry: Any) -> dict[str, Any] | None:
        if entry is None:
            return None
        if isinstance(entry, AssetRef):
            return entry.model_dump()
        if isinstance(entry, dict):
            return dict(entry)
        return {"value": entry}

    def _normalize_asset_list(self, entries: Iterable[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for entry in entries or []:
            normalized_entry = self._normalize_asset_entry(entry)
            if normalized_entry:
                normalized.append(normalized_entry)
        return normalized

    def _merge_registry(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        merged = self._empty_registry()
        merged["logo"] = override.get("logo") or base.get("logo")
        merged["style_refs"] = self._merge_asset_lists(base.get("style_refs"), override.get("style_refs"))
        merged["backgrounds"] = self._merge_asset_lists(
            base.get("backgrounds"), override.get("backgrounds")
        )
        merged["product_images"] = self._merge_asset_lists(
            base.get("product_images"), override.get("product_images")
        )
        return merged

    def _merge_asset_lists(self, left: Any, right: Any) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen = set()
        for entry in self._normalize_asset_list(left or []) + self._normalize_asset_list(right or []):
            key = entry.get("id") or entry.get("url") or entry.get("filename")
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            result.append(entry)
        return result

    def _copy_assets(self, registry: dict[str, Any], assets_payload: Any) -> dict[str, Any]:
        files_lookup = self._build_files_lookup(assets_payload)
        self.public_assets_dir.mkdir(parents=True, exist_ok=True)

        def handle_entry(entry: dict[str, Any]) -> None:
            source = self._resolve_asset_source(entry, files_lookup)
            if source is None:
                return
            filename = entry.get("filename") or source.name
            if not filename:
                return
            target = self.public_assets_dir / filename
            try:
                target.write_bytes(source.read_bytes())
            except OSError:
                logger.warning("Failed to copy asset %s", source)
                return
            entry["url"] = f"/assets/{filename}"
            if "path" in entry:
                entry.pop("path", None)
            if "filename" in entry:
                entry.pop("filename", None)

        for entry in self._iter_asset_entries(registry):
            handle_entry(entry)

        return registry

    def _iter_asset_entries(self, registry: dict[str, Any]) -> Iterable[dict[str, Any]]:
        for key in ("logo", "style_refs", "backgrounds", "product_images"):
            entry = registry.get(key)
            if entry is None:
                continue
            if isinstance(entry, list):
                for item in entry:
                    if isinstance(item, dict):
                        yield item
                continue
            if isinstance(entry, dict):
                yield entry

    def _build_files_lookup(self, assets_payload: Any) -> dict[str, dict[str, Any]]:
        lookup: dict[str, dict[str, Any]] = {}
        if not isinstance(assets_payload, dict):
            return lookup
        files = assets_payload.get("files") or []
        if not isinstance(files, list):
            return lookup
        for item in files:
            if not isinstance(item, dict):
                continue
            key = item.get("id") or item.get("filename") or item.get("name")
            if not key and item.get("path"):
                key = Path(str(item.get("path"))).name
            if not key:
                continue
            lookup[str(key)] = item
        return lookup

    def _resolve_asset_source(
        self,
        entry: dict[str, Any],
        files_lookup: dict[str, dict[str, Any]],
    ) -> Path | None:
        if entry.get("path"):
            return Path(str(entry.get("path")))

        lookup_key = entry.get("id") or entry.get("filename") or entry.get("url")
        if lookup_key and lookup_key in files_lookup:
            path_value = files_lookup[lookup_key].get("path")
            if path_value:
                return Path(str(path_value))

        if self.session_id and entry.get("id"):
            try:
                return AssetRegistryService(
                    self.session_id, base_dir=self._assets_base_path()
                ).get_asset_path(entry.get("id"))
            except FileNotFoundError:
                pass

        if self.session_id and entry.get("url"):
            url = str(entry.get("url"))
            filename = Path(url.split("?")[0]).name
            if filename:
                candidate = (
                    self._assets_base_path() / self.session_id / "assets" / filename
                )
                if candidate.exists():
                    return candidate

        return None

    def _empty_registry(self) -> dict[str, Any]:
        return {
            "logo": None,
            "style_refs": [],
            "backgrounds": [],
            "product_images": [],
        }

    def _normalize_slug(self, slug: Any) -> str:
        if not slug:
            return "index"
        cleaned = str(slug).strip().lstrip("/").rstrip("/")
        cleaned = cleaned.replace(".html", "")
        return cleaned or "index"

    def _safe_filename(self, slug: str) -> str:
        cleaned = slug.replace("/", "-")
        cleaned = cleaned.replace("..", "-")
        cleaned = cleaned.strip()
        return cleaned or "index"

    def _write_json(self, path: Path, payload: Any) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


__all__ = ["SchemaFileGenerator"]
