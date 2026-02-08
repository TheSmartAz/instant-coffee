from __future__ import annotations

import base64
import json
import logging
import os
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional

import httpx
from PIL import Image

from ..config import Settings, get_settings
from ..schemas.style_tokens import StyleTokens

logger = logging.getLogger(__name__)

STYLE_EXTRACTION_PROMPT = (
    "Analyze this image's visual design and return JSON with: "
    "colors (primary, secondary, accent, background, surface, text primary/secondary/muted), "
    "typography (fontFamily, scale: compact/normal/spacious), "
    "radius (none/small/medium/large/full), "
    "spacing (compact/normal/airy), "
    "shadow (none/subtle/medium/strong), "
    "style (modern/classic/playful/minimal/bold). "
    "Return only JSON."
)

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)

_DEFAULT_TOKENS = {
    "colors": {
        "primary": "#2563EB",
        "secondary": "#10B981",
        "accent": "#F59E0B",
        "background": "#FFFFFF",
        "surface": "#F3F4F6",
        "text": {
            "primary": "#111827",
            "secondary": "#6B7280",
            "muted": "#9CA3AF",
        },
    },
    "typography": {"fontFamily": "Inter, sans-serif", "scale": "normal"},
    "radius": "medium",
    "spacing": "normal",
    "shadow": "subtle",
    "style": "modern",
}


@dataclass
class _ResolvedImage:
    data: bytes
    content_type: str


class StyleExtractorService:
    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_version: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.api_key = api_key if api_key is not None else self.settings.anthropic_api_key
        self.model = model or self._resolve_default_model()
        self.base_url = base_url or self.settings.anthropic_base_url
        self.api_version = api_version or self.settings.anthropic_api_version
        self._timeout = timeout_seconds or self.settings.openai_timeout_seconds

    async def extract_style_tokens(self, image_url: str) -> Optional[StyleTokens]:
        if not image_url:
            return None
        image = await self._resolve_image(image_url)
        if image is None:
            return None

        tokens: Optional[StyleTokens] = None
        if self.api_key:
            try:
                tokens = await self._extract_with_vision(image)
            except Exception as exc:
                logger.warning("Vision extraction failed; falling back. Error: %s", exc)
                tokens = None
        if tokens is None:
            tokens = self._fallback_extract(image)
        return tokens

    def _resolve_default_model(self) -> str:
        env_model = os.getenv("ANTHROPIC_VISION_MODEL") or os.getenv("ANTHROPIC_MODEL")
        if env_model:
            return env_model
        configured = self.settings.model or ""
        if "claude" in configured.lower():
            return configured
        return "claude-3-5-sonnet-20240620"

    async def _extract_with_vision(self, image: _ResolvedImage) -> Optional[StyleTokens]:
        payload = {
            "model": self.model,
            "max_tokens": 800,
            "temperature": 0.2,
            "system": STYLE_EXTRACTION_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image.content_type,
                                "data": base64.b64encode(image.data).decode("ascii"),
                            },
                        },
                        {"type": "text", "text": "Return JSON only."},
                    ],
                }
            ],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self._timeout) as client:
            response = await client.post("/v1/messages", json=payload, headers=headers)
        if response.status_code >= 400:
            raise ValueError(f"Anthropic API error {response.status_code}: {response.text}")
        response_json = response.json()
        text = self._extract_text(response_json)
        if not text:
            return None
        payload = self._extract_json_payload(text)
        if payload is None:
            return None
        try:
            return StyleTokens.model_validate(payload)
        except Exception as exc:
            logger.warning("Invalid style token payload: %s", exc)
            return None

    async def _resolve_image(self, image_url: str) -> Optional[_ResolvedImage]:
        if image_url.startswith("http://") or image_url.startswith("https://"):
            return await self._load_remote_image(image_url)
        if image_url.startswith("file://"):
            path = Path(image_url.replace("file://", ""))
            return self._load_local_image(path)
        if image_url.startswith("/assets/"):
            path = self._resolve_assets_path(image_url)
            if path:
                return self._load_local_image(path)
        path = Path(image_url)
        if path.exists():
            return self._load_local_image(path)
        return None

    async def _load_remote_image(self, url: str) -> Optional[_ResolvedImage]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url)
        except httpx.HTTPError as exc:
            logger.warning("Failed to fetch image: %s", exc)
            return None
        if response.status_code >= 400:
            return None
        content_type = response.headers.get("content-type", "image/png").split(";")[0]
        return _ResolvedImage(data=response.content, content_type=content_type)

    def _load_local_image(self, path: Path) -> Optional[_ResolvedImage]:
        if not path.exists() or not path.is_file():
            return None
        content_type = self._content_type_from_path(path)
        return _ResolvedImage(data=path.read_bytes(), content_type=content_type)

    def _resolve_assets_path(self, image_url: str) -> Optional[Path]:
        parts = image_url.strip("/").split("/")
        if len(parts) < 3 or parts[0] != "assets":
            return None
        session_id = parts[1]
        filename = "/".join(parts[2:])
        base = Path("~/.instant-coffee/sessions").expanduser()
        path = base / session_id / "assets" / filename
        if path.exists():
            return path
        return None

    def _content_type_from_path(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".png":
            return "image/png"
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        if suffix == ".svg":
            return "image/svg+xml"
        return "application/octet-stream"

    def _extract_text(self, response_json: dict) -> str:
        if isinstance(response_json, dict):
            content = response_json.get("content") or []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text")
                    if text:
                        return str(text).strip()
        return ""

    def _extract_json_payload(self, raw_text: str) -> Optional[dict]:
        if not raw_text:
            return None
        fenced = _JSON_BLOCK.search(raw_text)
        if fenced:
            try:
                return json.loads(fenced.group(1))
            except json.JSONDecodeError:
                pass

        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        snippet = raw_text[start : end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            return None

    def _fallback_extract(self, image: _ResolvedImage) -> StyleTokens:
        palette = self._extract_palette(image.data)
        primary = palette[1] if len(palette) > 1 else _DEFAULT_TOKENS["colors"]["primary"]
        secondary = palette[2] if len(palette) > 2 else _DEFAULT_TOKENS["colors"]["secondary"]
        accent = palette[3] if len(palette) > 3 else _DEFAULT_TOKENS["colors"]["accent"]
        background = palette[0] if palette else _DEFAULT_TOKENS["colors"]["background"]
        surface = self._adjust_color(background, 0.1)
        text_primary = self._pick_text_color(background)
        text_secondary = self._adjust_color(text_primary, -0.25)
        text_muted = self._adjust_color(text_primary, -0.45)

        payload = {
            "colors": {
                "primary": primary,
                "secondary": secondary,
                "accent": accent,
                "background": background,
                "surface": surface,
                "text": {
                    "primary": text_primary,
                    "secondary": text_secondary,
                    "muted": text_muted,
                },
            },
            "typography": _DEFAULT_TOKENS["typography"],
            "radius": _DEFAULT_TOKENS["radius"],
            "spacing": _DEFAULT_TOKENS["spacing"],
            "shadow": _DEFAULT_TOKENS["shadow"],
            "style": _DEFAULT_TOKENS["style"],
        }
        return StyleTokens.model_validate(payload)

    def _extract_palette(self, data: bytes) -> list[str]:
        try:
            with Image.open(BytesIO(data)) as image:
                image = image.convert("RGB")
                image.thumbnail((64, 64))
                colors = image.getcolors(maxcolors=64 * 64) or []
        except Exception:
            return [
                _DEFAULT_TOKENS["colors"]["background"],
                _DEFAULT_TOKENS["colors"]["primary"],
                _DEFAULT_TOKENS["colors"]["secondary"],
                _DEFAULT_TOKENS["colors"]["accent"],
            ]

        colors_sorted = sorted(colors, key=lambda item: item[0], reverse=True)
        palette = []
        for _, rgb in colors_sorted:
            hex_value = self._rgb_to_hex(rgb)
            if hex_value not in palette:
                palette.append(hex_value)
            if len(palette) >= 4:
                break
        return palette

    def _rgb_to_hex(self, rgb: tuple[int, int, int]) -> str:
        return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"

    def _pick_text_color(self, background: str) -> str:
        lum = self._luminance(background)
        return "#111827" if lum > 0.5 else "#F9FAFB"

    def _luminance(self, hex_color: str) -> float:
        rgb = self._hex_to_rgb(hex_color)
        if rgb is None:
            return 1.0
        r, g, b = [value / 255.0 for value in rgb]
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def _adjust_color(self, hex_color: str, amount: float) -> str:
        rgb = self._hex_to_rgb(hex_color)
        if rgb is None:
            return hex_color
        def clamp(value: float) -> int:
            return max(0, min(255, int(round(value))))
        if amount >= 0:
            adjusted = tuple(clamp(channel + (255 - channel) * amount) for channel in rgb)
        else:
            adjusted = tuple(clamp(channel * (1 + amount)) for channel in rgb)
        return self._rgb_to_hex(adjusted)

    def _hex_to_rgb(self, hex_color: str) -> Optional[tuple[int, int, int]]:
        if not hex_color:
            return None
        value = hex_color.strip().lstrip("#")
        if len(value) != 6:
            return None
        try:
            return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            return None


__all__ = ["StyleExtractorService", "StyleTokens", "STYLE_EXTRACTION_PROMPT"]
