from __future__ import annotations

import json
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image

from ..utils.datetime import utcnow
from ..schemas.asset import AssetRef, AssetRegistry, AssetType

_ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/svg+xml",
}
_MAX_ASSET_BYTES = 10 * 1024 * 1024

_EXTENSION_BY_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}

_MIME_BY_EXTENSION = {v: k for k, v in _EXTENSION_BY_MIME.items()}

_SVG_NUMBER = re.compile(r"([0-9]+(?:\.[0-9]+)?)")


@dataclass
class AssetMeta:
    asset_id: str
    filename: str
    content_type: str
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: Optional[str] = None


class AssetRegistryService:
    def __init__(self, session_id: str, base_dir: Optional[Path] = None) -> None:
        if not session_id:
            raise ValueError("session_id is required")
        self.session_id = session_id
        base = base_dir or Path("~/.instant-coffee/sessions").expanduser()
        self.base_path = (base / session_id / "assets").resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def register_asset(self, file: UploadFile, asset_type: AssetType | str) -> AssetRef:
        asset_type_value = self._normalize_asset_type(asset_type)

        payload = await file.read()
        if not payload:
            raise ValueError("asset file is empty")
        if len(payload) > _MAX_ASSET_BYTES:
            raise ValueError("asset file exceeds 10MB limit")

        filename = file.filename or ""
        extension = Path(filename).suffix.lower()
        content_type = file.content_type or ""

        if not extension:
            extension = _EXTENSION_BY_MIME.get(content_type, "")
        if not content_type:
            content_type = self._content_type_for_extension(extension)

        if content_type not in _ALLOWED_MIME_TYPES:
            raise ValueError("unsupported asset type")
        if not extension:
            extension = _EXTENSION_BY_MIME.get(content_type, "")
        if not extension:
            raise ValueError("unable to determine asset extension")

        asset_id = self._generate_asset_id(asset_type_value)
        file_path = self.base_path / f"{asset_id}{extension}"

        file_path.write_bytes(payload)

        width, height = self._detect_dimensions(file_path, content_type)
        meta = AssetMeta(
            asset_id=asset_id,
            filename=file_path.name,
            content_type=content_type,
            width=width,
            height=height,
            created_at=utcnow().isoformat(),
        )
        self._write_meta(meta)

        return AssetRef(
            id=f"asset:{asset_id}",
            url=f"/assets/{self.session_id}/{file_path.name}",
            type=content_type,
            width=width,
            height=height,
        )

    def get_registry(self) -> AssetRegistry:
        if not self.base_path.exists():
            return AssetRegistry()

        registry = AssetRegistry()
        logo_candidates: list[tuple[AssetRef, float]] = []
        style_refs: list[tuple[AssetRef, float]] = []
        backgrounds: list[tuple[AssetRef, float]] = []
        product_images: list[tuple[AssetRef, float]] = []

        for path in self.base_path.iterdir():
            if not path.is_file():
                continue
            if path.suffix.lower() == ".json":
                continue
            asset_id = path.stem
            asset_type = self._parse_asset_type(asset_id)
            if asset_type is None:
                continue
            meta = self._read_meta(asset_id)
            content_type = (meta.content_type if meta else None) or self._content_type_for_extension(path.suffix)
            width = meta.width if meta else None
            height = meta.height if meta else None
            if width is None or height is None:
                detected_width, detected_height = self._detect_dimensions(path, content_type)
                width = width or detected_width
                height = height or detected_height

            asset_ref = AssetRef(
                id=f"asset:{asset_id}",
                url=f"/assets/{self.session_id}/{path.name}",
                type=content_type,
                width=width,
                height=height,
            )
            modified = path.stat().st_mtime
            if asset_type == AssetType.logo:
                logo_candidates.append((asset_ref, modified))
            elif asset_type == AssetType.style_ref:
                style_refs.append((asset_ref, modified))
            elif asset_type == AssetType.background:
                backgrounds.append((asset_ref, modified))
            elif asset_type == AssetType.product_image:
                product_images.append((asset_ref, modified))

        if logo_candidates:
            logo_candidates.sort(key=lambda item: item[1], reverse=True)
            registry.logo = logo_candidates[0][0]
        registry.style_refs = [ref for ref, _ in sorted(style_refs, key=lambda item: item[1])]
        registry.backgrounds = [ref for ref, _ in sorted(backgrounds, key=lambda item: item[1])]
        registry.product_images = [ref for ref, _ in sorted(product_images, key=lambda item: item[1])]
        return registry

    def get_asset_meta(self, asset_id: str) -> Optional[AssetMeta]:
        normalized = asset_id
        if normalized.startswith("asset:"):
            normalized = normalized.split("asset:", 1)[1]
        meta = self._read_meta(normalized)
        if meta is not None:
            return meta
        try:
            path = self.get_asset_path(normalized)
        except FileNotFoundError:
            return None
        width, height = self._detect_dimensions(path, self._content_type_for_extension(path.suffix))
        return AssetMeta(
            asset_id=path.stem,
            filename=path.name,
            content_type=self._content_type_for_extension(path.suffix),
            width=width,
            height=height,
            created_at=None,
        )

    def delete_asset(self, asset_id: str) -> bool:
        try:
            path = self.get_asset_path(asset_id)
        except FileNotFoundError:
            return False
        asset_stem = path.stem
        try:
            path.unlink()
        except OSError:
            return False
        meta_path = self._meta_path(asset_stem)
        try:
            if meta_path.exists():
                meta_path.unlink()
        except OSError:
            pass
        return True

    def get_asset_path(self, asset_id: str) -> Path:
        if not asset_id:
            raise FileNotFoundError("asset_id is required")
        normalized = asset_id
        if normalized.startswith("asset:"):
            normalized = normalized.split("asset:", 1)[1]
        asset_path = self.base_path / normalized
        if asset_path.exists():
            return asset_path
        for path in self.base_path.glob(f"{normalized}.*"):
            if path.is_file():
                return path
        raise FileNotFoundError(f"asset not found: {asset_id}")

    def _normalize_asset_type(self, asset_type: AssetType | str) -> str:
        if isinstance(asset_type, AssetType):
            return asset_type.value
        try:
            return AssetType(str(asset_type)).value
        except ValueError as exc:
            raise ValueError("invalid asset type") from exc

    def _generate_asset_id(self, asset_type: str) -> str:
        for _ in range(10):
            candidate = f"{asset_type}_{uuid4().hex[:8]}"
            if not any(self.base_path.glob(f"{candidate}.*")):
                return candidate
        raise RuntimeError("unable to generate unique asset id")

    def _parse_asset_type(self, asset_id: str) -> Optional[AssetType]:
        if not asset_id or "_" not in asset_id:
            return None
        for asset_type in AssetType:
            if asset_id.startswith(f"{asset_type.value}_"):
                return asset_type
        return None

    def _meta_path(self, asset_id: str) -> Path:
        return self.base_path / f"{asset_id}.json"

    def _write_meta(self, meta: AssetMeta) -> None:
        payload = {
            "id": meta.asset_id,
            "filename": meta.filename,
            "content_type": meta.content_type,
            "width": meta.width,
            "height": meta.height,
            "created_at": meta.created_at,
        }
        self._meta_path(meta.asset_id).write_text(json.dumps(payload), encoding="utf-8")

    def _read_meta(self, asset_id: str) -> Optional[AssetMeta]:
        path = self._meta_path(asset_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return AssetMeta(
            asset_id=payload.get("id") or asset_id,
            filename=payload.get("filename") or "",
            content_type=payload.get("content_type") or "application/octet-stream",
            width=payload.get("width"),
            height=payload.get("height"),
            created_at=payload.get("created_at"),
        )

    def _content_type_for_extension(self, extension: str) -> str:
        if not extension:
            return "application/octet-stream"
        normalized = extension.lower()
        if normalized in _MIME_BY_EXTENSION:
            return _MIME_BY_EXTENSION[normalized]
        guessed, _ = mimetypes.guess_type(f"file{normalized}")
        return guessed or "application/octet-stream"

    def _detect_dimensions(self, path: Path, content_type: str) -> tuple[Optional[int], Optional[int]]:
        if content_type == "image/svg+xml" or path.suffix.lower() == ".svg":
            return self._detect_svg_dimensions(path)
        try:
            with Image.open(path) as image:
                width, height = image.size
                return int(width), int(height)
        except Exception:
            return None, None

    def _detect_svg_dimensions(self, path: Path) -> tuple[Optional[int], Optional[int]]:
        try:
            import xml.etree.ElementTree as ET

            tree = ET.parse(path)
            root = tree.getroot()
            width = self._parse_svg_number(root.get("width"))
            height = self._parse_svg_number(root.get("height"))
            if width is not None and height is not None:
                return width, height
            view_box = root.get("viewBox") or root.get("viewbox")
            if view_box:
                parts = re.split(r"[ ,]+", view_box.strip())
                if len(parts) >= 4:
                    width = self._parse_svg_number(parts[2])
                    height = self._parse_svg_number(parts[3])
                    return width, height
        except Exception:
            return None, None
        return None, None

    def _parse_svg_number(self, raw: Optional[str]) -> Optional[int]:
        if not raw:
            return None
        match = _SVG_NUMBER.search(str(raw))
        if not match:
            return None
        try:
            value = float(match.group(1))
        except ValueError:
            return None
        return int(round(value))


__all__ = ["AssetRegistryService"]
