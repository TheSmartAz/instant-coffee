from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from uuid import uuid4
from ..utils.datetime import utcnow

_DATA_URL_PATTERN = re.compile(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$", re.DOTALL)

_EXTENSION_BY_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


@dataclass
class StoredImage:
    id: str
    path: Path
    content_type: str
    created_at: datetime
    url: Optional[str] = None


class ImageStorageService:
    def __init__(self, storage_dir: str, ttl_seconds: int = 3600) -> None:
        self.storage_dir = Path(storage_dir).expanduser().resolve(strict=False)
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def is_url(value: str) -> bool:
        if not value:
            return False
        lowered = value.lower()
        return lowered.startswith("http://") or lowered.startswith("https://")

    def _session_dir(self, session_id: str) -> Path:
        path = self.storage_dir / session_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _decode_image(self, data: str) -> tuple[bytes, str]:
        if not data:
            raise ValueError("image data is required")
        content_type = "application/octet-stream"
        payload = data.strip()
        if payload.startswith("data:"):
            match = _DATA_URL_PATTERN.match(payload)
            if not match:
                raise ValueError("invalid data URL")
            content_type = match.group("mime") or content_type
            payload = match.group("data")
        payload = re.sub(r"\s+", "", payload)
        if not payload:
            raise ValueError("image data is required")
        padding = "=" * (-len(payload) % 4)
        payload += padding
        try:
            raw = base64.b64decode(payload, validate=True)
        except binascii.Error as exc:
            raise ValueError("invalid base64 image data") from exc
        return raw, content_type

    def _extension_for(self, content_type: str) -> str:
        if not content_type:
            return ".bin"
        return _EXTENSION_BY_MIME.get(content_type.lower(), ".bin")

    def _meta_path(self, session_dir: Path, image_id: str) -> Path:
        return session_dir / f"{image_id}.json"

    def _resolve_session_id(self, image_id: str) -> Optional[str]:
        if not image_id:
            return None
        parts = image_id.split("_", 1)
        if len(parts) != 2:
            return None
        return parts[0]

    def _is_expired(self, created_at: datetime) -> bool:
        return created_at + timedelta(seconds=self.ttl_seconds) < utcnow()

    async def save_image(self, data: str, session_id: str) -> StoredImage:
        raw, content_type = self._decode_image(data)
        session_dir = self._session_dir(session_id)
        image_id = f"{session_id}_{uuid4().hex[:8]}"
        extension = self._extension_for(content_type)
        image_path = session_dir / f"{image_id}{extension}"
        image_path.write_bytes(raw)
        created_at = utcnow()
        meta = {
            "id": image_id,
            "filename": image_path.name,
            "content_type": content_type,
            "created_at": created_at.isoformat(),
        }
        meta_path = self._meta_path(session_dir, image_id)
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        return StoredImage(
            id=image_id,
            path=image_path,
            content_type=content_type,
            created_at=created_at,
            url=image_path.as_uri(),
        )

    async def get_image(self, image_id: str) -> Optional[dict]:
        session_id = self._resolve_session_id(image_id)
        if session_id is None:
            return None
        session_dir = self.storage_dir / session_id
        meta_path = self._meta_path(session_dir, image_id)
        if not meta_path.exists():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        created_at_raw = meta.get("created_at")
        try:
            created_at = datetime.fromisoformat(created_at_raw)
        except (TypeError, ValueError):
            created_at = None
        if created_at and self._is_expired(created_at):
            await self._delete_image_files(session_dir, image_id, meta)
            return None
        filename = meta.get("filename")
        if not filename:
            return None
        image_path = session_dir / filename
        if not image_path.exists():
            return None
        data = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return {
            "id": image_id,
            "data": data,
            "content_type": meta.get("content_type") or "application/octet-stream",
            "created_at": created_at_raw,
        }

    async def cleanup_session(self, session_id: str) -> None:
        session_dir = self.storage_dir / session_id
        if not session_dir.exists():
            return
        for path in session_dir.iterdir():
            try:
                if path.is_file():
                    path.unlink()
            except OSError:
                continue
        try:
            session_dir.rmdir()
        except OSError:
            return

    async def _delete_image_files(self, session_dir: Path, image_id: str, meta: dict) -> None:
        filename = meta.get("filename")
        if filename:
            path = session_dir / filename
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass
        meta_path = self._meta_path(session_dir, image_id)
        try:
            if meta_path.exists():
                meta_path.unlink()
        except OSError:
            pass


__all__ = ["ImageStorageService", "StoredImage"]
