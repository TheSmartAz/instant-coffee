from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Optional

from ..config import Settings, get_settings
from .model_catalog import get_model_entry
from .openai_client import OpenAIClient, OpenAIClientError

logger = logging.getLogger(__name__)


class ModelClientFactoryError(RuntimeError):
    """Raised when model client creation fails."""


@dataclass(frozen=True)
class ModelClientConfig:
    model_id: str
    base_url: Optional[str]
    api_key: Optional[str]


class ModelClientFactory:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._cache: dict[tuple[str, str, str], OpenAIClient] = {}

    def create(
        self,
        *,
        model_id: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> OpenAIClient:
        if not model_id:
            raise ModelClientFactoryError("model_id is required to create a model client")

        resolved_base_url = base_url or self._resolve_base_url(model_id)
        resolved_key = api_key or self._resolve_api_key()
        if not resolved_key:
            raise ModelClientFactoryError("API key is not configured for model client")
        if not resolved_base_url:
            raise ModelClientFactoryError("Base URL is not configured for model client")

        cache_key = (model_id, resolved_base_url, self._hash_key(resolved_key))
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            client = OpenAIClient(
                settings=self._settings,
                api_key=resolved_key,
                base_url=resolved_base_url,
                model=model_id,
            )
        except OpenAIClientError as exc:
            raise ModelClientFactoryError(str(exc)) from exc

        self._cache[cache_key] = client
        return client

    def _resolve_base_url(self, model_id: str) -> str | None:
        entry = get_model_entry(model_id)
        if entry and entry.get("base_url"):
            return entry["base_url"]
        return self._settings.openai_base_url or self._settings.default_base_url

    def _resolve_api_key(self) -> str | None:
        return self._settings.openai_api_key or self._settings.default_key

    def _hash_key(self, value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return digest[:16]


__all__ = ["ModelClientFactory", "ModelClientFactoryError", "ModelClientConfig"]
