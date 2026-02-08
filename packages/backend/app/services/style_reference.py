from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from ..agents.prompts import get_style_reference_prompt
from ..config import Settings, get_settings
from ..llm.client_factory import ModelClientFactory
from ..llm.model_catalog import model_supports_capability
from ..llm.model_pool import FallbackTrigger, ModelRole, get_model_pool_manager
from ..llm.openai_client import OpenAIClient
from ..schemas.style_reference import StyleImage, StyleScope, StyleTokens
from ..services.image_storage import ImageStorageService
from ..utils.style import normalize_hex_color

logger = logging.getLogger(__name__)

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)

_RADIUS_MAP = {
    "sharp": "0px",
    "small": "4px",
    "medium": "8px",
    "large": "16px",
    "pill": "999px",
}

_SPACING_MAP = {
    "tight": "6px",
    "medium": "8px",
    "airy": "12px",
}

_HEADING_SCALE_MAP = {
    "small": "22px",
    "base": "24px",
    "large": "28px",
    "xlarge": "32px",
}

_BASE_SCALE_MAP = {
    "small": "14px",
    "base": "16px",
    "large": "18px",
    "xlarge": "20px",
}


def _coerce_mapping(value: Any) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()  # type: ignore[return-value]
    if hasattr(value, "dict"):
        return value.dict()  # type: ignore[return-value]
    return {}


def merge_style_tokens(base: Optional[dict], override: Optional[dict]) -> dict:
    base = _coerce_mapping(base)
    override = _coerce_mapping(override)
    if not base:
        return override
    if not override:
        return base

    def _merge(left: Any, right: Any) -> Any:
        if isinstance(left, dict) and isinstance(right, dict):
            merged = dict(left)
            for key, value in right.items():
                if key in merged:
                    merged[key] = _merge(merged[key], value)
                else:
                    merged[key] = value
            return merged
        if isinstance(right, list):
            return right or left
        return right if right is not None else left

    return _merge(base, override)


def normalize_style_tokens(tokens: Optional[dict]) -> dict:
    payload = _coerce_mapping(tokens)
    if not payload:
        return {}

    colors = payload.get("colors") if isinstance(payload.get("colors"), dict) else {}
    typography = payload.get("typography") if isinstance(payload.get("typography"), dict) else {}

    if "background" in colors or "text" in colors:
        return payload

    bg = colors.get("bg") or colors.get("background")
    surface = colors.get("surface")
    primary = colors.get("primary")
    accent = colors.get("accent")
    muted = colors.get("muted")

    background: Dict[str, Any] = {}
    if bg:
        background["main"] = bg
    if surface:
        background["surface"] = surface
        background.setdefault("card", surface)

    text: Dict[str, Any] = {}
    if primary:
        text["primary"] = primary
    if muted:
        text["secondary"] = muted

    normalized_colors = {
        "primary": primary,
        "accent": accent or primary,
        "background": background if background else None,
        "text": text if text else None,
        "border": muted,
    }

    normalized_colors = {k: v for k, v in normalized_colors.items() if v}

    heading = typography.get("heading") if isinstance(typography.get("heading"), dict) else {}
    body = typography.get("body") if isinstance(typography.get("body"), dict) else {}
    family = typography.get("family") or heading.get("family") or body.get("family")
    scale = typography.get("scale")

    normalized_typography: Dict[str, Any] = {
        "family": family,
        "scale": scale,
        "weights": typography.get("weights") or [],
    }
    normalized_typography = {k: v for k, v in normalized_typography.items() if v}

    radius = payload.get("radius")
    shadow = payload.get("shadow")
    spacing = payload.get("spacing")

    radius_map = {"sharp", "small", "medium", "large", "pill"}
    shadow_map = {"none", "soft", "medium", "strong"}
    spacing_map = {"tight", "medium", "airy"}

    if isinstance(radius, str) and radius not in radius_map:
        radius = "medium"
    if isinstance(shadow, str) and shadow not in shadow_map:
        shadow = "soft"
    if isinstance(spacing, str) and spacing not in spacing_map:
        if spacing in {"compact", "tight"}:
            spacing = "tight"
        elif spacing in {"relaxed", "airy"}:
            spacing = "airy"
        else:
            spacing = "medium"

    normalized = dict(payload)
    normalized.update(
        {
            "colors": normalized_colors,
            "typography": normalized_typography,
        }
    )
    if radius:
        normalized["radius"] = radius
    if shadow:
        normalized["shadow"] = shadow
    if spacing:
        normalized["spacing"] = spacing
    return normalized


def tokens_to_global_style(tokens: Optional[dict]) -> dict:
    payload = _coerce_mapping(tokens)
    if not payload:
        return {}

    colors = payload.get("colors") if isinstance(payload.get("colors"), dict) else {}
    typography = payload.get("typography") if isinstance(payload.get("typography"), dict) else {}

    primary = colors.get("primary") or colors.get("accent")
    secondary = colors.get("accent") or colors.get("primary")

    primary = normalize_hex_color(primary, None)
    secondary = normalize_hex_color(secondary, None)

    family = (
        typography.get("family")
        or (typography.get("heading") or {}).get("family")
        or (typography.get("body") or {}).get("family")
    )

    scale = typography.get("scale")
    heading_size = _HEADING_SCALE_MAP.get(str(scale).lower()) if isinstance(scale, str) else None
    base_size = _BASE_SCALE_MAP.get(str(scale).lower()) if isinstance(scale, str) else None

    radius_value = payload.get("radius")
    spacing_value = payload.get("spacing")

    global_style: dict = {}
    if primary:
        global_style["primary_color"] = primary
    if secondary:
        global_style["secondary_color"] = secondary
    if family:
        global_style["font_family"] = str(family)
    if heading_size:
        global_style["font_size_heading"] = heading_size
    if base_size:
        global_style["font_size_base"] = base_size
    if radius_value:
        radius_key = str(radius_value).lower()
        if radius_key in _RADIUS_MAP:
            global_style["border_radius"] = _RADIUS_MAP[radius_key]
    if spacing_value:
        spacing_key = str(spacing_value).lower()
        if spacing_key in _SPACING_MAP:
            global_style["spacing_unit"] = _SPACING_MAP[spacing_key]

    return global_style


def parse_style_tokens(raw_text: str) -> StyleTokens:
    payload = _extract_json_payload(raw_text)
    if payload is None:
        raise ValueError("No JSON object found in style reference response")
    try:
        return StyleTokens.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Invalid style token payload: {exc}") from exc


def _extract_json_payload(raw_text: str) -> Optional[dict]:
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


def _hex_to_rgb(value: str) -> Optional[tuple[int, int, int]]:
    if not value:
        return None
    value = value.strip()
    if value.startswith("#"):
        value = value[1:]
    if len(value) != 6:
        return None
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return None


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def _channel(value: int) -> float:
        channel = value / 255.0
        return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def _contrast_ratio(color_a: str, color_b: str) -> Optional[float]:
    rgb_a = _hex_to_rgb(color_a)
    rgb_b = _hex_to_rgb(color_b)
    if rgb_a is None or rgb_b is None:
        return None
    lum_a = _relative_luminance(rgb_a)
    lum_b = _relative_luminance(rgb_b)
    lighter = max(lum_a, lum_b)
    darker = min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def _pick_color(colors: dict, *keys: str) -> Optional[str]:
    for key in keys:
        value = colors.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _extract_text_and_background(colors: dict) -> tuple[Optional[str], Optional[str]]:
    text = colors.get("text") if isinstance(colors.get("text"), dict) else {}
    background = colors.get("background") if isinstance(colors.get("background"), dict) else {}
    text_color = _pick_color(text, "primary", "secondary") or _pick_color(colors, "primary")
    background_color = _pick_color(background, "main", "surface", "card") or _pick_color(colors, "background")
    return text_color, background_color


def _passes_contrast(tokens: dict, threshold: float = 4.5) -> bool:
    colors = tokens.get("colors") if isinstance(tokens.get("colors"), dict) else {}
    if not colors:
        return True
    text_color, background_color = _extract_text_and_background(colors)
    if not text_color or not background_color:
        return True
    ratio = _contrast_ratio(text_color, background_color)
    if ratio is None:
        return True
    return ratio >= threshold


class StyleReferenceService:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        vision_client: Optional[OpenAIClient] = None,
        vision_model: Optional[str] = None,
        model_pool=None,
        product_type: Optional[str] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = vision_client
        self._vision_model = vision_model
        self._model_pool = model_pool or get_model_pool_manager(self.settings)
        self._product_type = product_type
        self._client_factory: Optional[ModelClientFactory] = None

    def _get_client(self) -> OpenAIClient:
        if self._client is None:
            self._client = OpenAIClient(settings=self.settings)
        return self._client

    def _get_factory(self) -> ModelClientFactory:
        if self._client_factory is None:
            self._client_factory = ModelClientFactory(self.settings)
        return self._client_factory

    def _use_chat_completions(self, client: OpenAIClient) -> bool:
        mode = getattr(self.settings, "openai_api_mode", "responses") or "responses"
        normalized = str(mode).strip().lower()
        if normalized in {"chat", "chat_completions", "chat-completions", "completions"}:
            return True
        return not client.supports_responses()

    async def extract_style(
        self,
        images: List[StyleImage],
        mode: str = "full_mimic",
        product_type: Optional[str] = None,
    ) -> Optional[StyleTokens]:
        if not images:
            return None
        if not await self.check_vision_capability(product_type=product_type):
            logger.warning("Vision model not available; skipping style reference extraction")
            return None

        resolved_mode = mode if mode in {"full_mimic", "style_only"} else "full_mimic"
        tokens = await self._extract_with_mode(images, resolved_mode, product_type=product_type)
        if tokens is None and resolved_mode == "full_mimic":
            logger.warning("Full-mimic extraction failed; retrying in style-only mode")
            tokens = await self._extract_with_mode(images, "style_only", product_type=product_type)
        return tokens

    async def _extract_with_mode(
        self,
        images: List[StyleImage],
        mode: str,
        *,
        product_type: Optional[str] = None,
    ) -> Optional[StyleTokens]:
        prompt = get_style_reference_prompt(mode)
        resolved_product_type = product_type or self._product_type

        async def _call_with_client(model_id: str, client: OpenAIClient) -> Optional[StyleTokens]:
            content_items = await self._build_content_items(
                images,
                use_chat=self._use_chat_completions(client),
            )
            if not content_items:
                return None
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": content_items},
            ]
            response = await (
                client.chat_completion
                if self._use_chat_completions(client)
                else client.responses_create
            )(
                messages=messages,
                model=model_id,
                temperature=0.2,
                max_tokens=1200,
            )

            try:
                tokens = parse_style_tokens(response.content or "")
            except ValueError as exc:
                logger.warning("Failed to parse style reference tokens: %s", exc)
                return None

            tokens_payload = tokens.model_dump()
            if not _passes_contrast(tokens_payload):
                logger.warning("Style reference tokens failed WCAG contrast; ignoring tokens")
                return None

            return tokens

        if self._model_pool:
            def _checker(result: Optional[StyleTokens]) -> Optional[FallbackTrigger]:
                if result is None:
                    return FallbackTrigger.INVALID_STRUCTURE
                return None

            result = await self._model_pool.run_with_fallback(
                role=ModelRole.STYLE_REFINER.value,
                product_type=resolved_product_type,
                preferred_model=self._vision_model,
                call=_call_with_client,
                response_checker=_checker,
                required_capabilities=["vision"],
            )
            return result.result

        model_id, client = self._resolve_client_and_model()
        return await _call_with_client(model_id, client)

    def apply_scope(
        self,
        tokens: StyleTokens | dict,
        scope: StyleScope | dict | None,
        target_pages: Optional[List[str]] = None,
    ) -> Dict[str, dict]:
        tokens_payload = _coerce_mapping(tokens)
        if not tokens_payload:
            return {}

        if scope is None:
            scope_obj = StyleScope()
        elif isinstance(scope, StyleScope):
            scope_obj = scope
        else:
            scope_obj = StyleScope.model_validate(scope)

        target_pages = [str(page).strip() for page in (target_pages or []) if str(page).strip()]
        if scope_obj.type == "specific_pages":
            pages = scope_obj.pages or target_pages
        else:
            pages = target_pages

        if pages:
            return {page: tokens_payload for page in pages}
        return {}

    async def check_vision_capability(self, *, product_type: Optional[str] = None) -> bool:
        model_id = self._vision_model or self.settings.model or ""
        if self._model_pool and not self._vision_model:
            candidates = self._model_pool.get_candidate_model_ids(
                role=ModelRole.STYLE_REFINER.value,
                product_type=product_type or self._product_type,
            )
            return any(model_supports_capability(model, "vision") for model in candidates)
        if not model_id:
            return False
        return model_supports_capability(model_id, "vision")

    def _resolve_client_and_model(self) -> tuple[str, OpenAIClient]:
        if self._client is not None:
            return self._vision_model or self.settings.model, self._client
        model_id = self._vision_model or self.settings.model
        if self._vision_model:
            client = self._get_factory().create(model_id=self._vision_model)
            return self._vision_model, client
        return model_id, self._get_client()

    async def _build_content_items(self, images: List[StyleImage], *, use_chat: bool) -> List[dict]:
        text_type = "text" if use_chat else "input_text"
        image_type = "image_url" if use_chat else "input_image"

        content_items: List[dict] = [
            {
                "type": text_type,
                "text": "Analyze each reference image. If a page_hint is provided, use it to scope layout patterns.",
            }
        ]

        for index, image in enumerate(images, start=1):
            image_url = await self._resolve_image_url(image)
            if not image_url:
                logger.warning("Missing image data for style reference image %s", image.id or index)
                continue
            hint = str(image.page_hint).strip() if image.page_hint else ""
            label = f"Reference image {index}"
            if hint:
                label = f"Reference image {index} (page_hint: {hint})"
            content_items.append({"type": text_type, "text": label})
            if use_chat:
                content_items.append({"type": image_type, "image_url": {"url": image_url}})
            else:
                content_items.append({"type": image_type, "image_url": image_url})

        return content_items

    async def _resolve_image_url(self, image: StyleImage) -> Optional[str]:
        if image.base64_data:
            return self._format_data_url(image.base64_data, image.content_type)

        if image.source == "upload" and image.id:
            image_data = await self._load_image_data(image.id)
            if image_data:
                return self._format_data_url(image_data["data"], image_data.get("content_type"))

        if image.url:
            if ImageStorageService.is_url(image.url):
                return image.url
            if image.url.startswith("file://"):
                path = Path(image.url.replace("file://", ""))
                if path.exists():
                    data = base64.b64encode(path.read_bytes()).decode("ascii")
                    return self._format_data_url(data, image.content_type)
        return None

    async def _load_image_data(self, image_id: str) -> Optional[dict]:
        storage_dir = Path(self.settings.output_dir) / "image-uploads"
        storage = ImageStorageService(str(storage_dir))
        return await storage.get_image(image_id)

    def _format_data_url(self, raw_data: str, content_type: Optional[str]) -> str:
        if raw_data.startswith("data:"):
            return raw_data
        resolved_type = content_type or "image/png"
        return f"data:{resolved_type};base64,{raw_data}"


__all__ = [
    "StyleReferenceService",
    "merge_style_tokens",
    "normalize_style_tokens",
    "parse_style_tokens",
    "tokens_to_global_style",
]
