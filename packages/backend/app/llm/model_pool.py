from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Iterable, Optional

from ..config import Settings, get_model_aliases, get_settings
from .client_factory import ModelClientFactory, ModelClientFactoryError
from .model_catalog import model_supports_capability
from .openai_client import APIError, OpenAIClient, TimeoutError

logger = logging.getLogger(__name__)


class ModelRole(str, Enum):
    CLASSIFIER = "classifier"
    WRITER = "writer"
    EXPANDER = "expander"
    VALIDATOR = "validator"
    STYLE_REFINER = "style_refiner"


class FallbackTrigger(str, Enum):
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    VALIDATOR_HARD_FAIL = "validator_hard_fail"
    MISSING_FIELD = "missing_field"
    INVALID_STRUCTURE = "invalid_structure"


class ModelExhaustedError(RuntimeError):
    """Raised when no models remain for the requested role."""


class ModelSelectionError(RuntimeError):
    """Raised when model selection fails unexpectedly."""


@dataclass(frozen=True)
class ModelSelection:
    model_id: str
    client: OpenAIClient


@dataclass(frozen=True)
class ModelCallResult:
    model_id: str
    result: Any


def should_fallback(
    error: Exception | None,
    response: Any,
    role: str,
) -> Optional[FallbackTrigger]:
    if error is not None:
        if isinstance(error, TimeoutError):
            return FallbackTrigger.TIMEOUT
        if isinstance(error, APIError):
            return FallbackTrigger.CONNECTION_ERROR
        if isinstance(error, ConnectionError):
            return FallbackTrigger.CONNECTION_ERROR
        return None

    if response is None:
        return None

    validator_result = getattr(response, "validator_result", None)
    if validator_result is not None:
        hard_fail = getattr(validator_result, "hard_fail", None)
        if hard_fail:
            return FallbackTrigger.VALIDATOR_HARD_FAIL

    if isinstance(response, dict):
        if response.get("validator_hard_fail"):
            return FallbackTrigger.VALIDATOR_HARD_FAIL
        if response.get("missing_fields") or response.get("missing_required"):
            return FallbackTrigger.MISSING_FIELD
        if response.get("invalid_structure"):
            return FallbackTrigger.INVALID_STRUCTURE

    if role == ModelRole.WRITER.value:
        missing_fields = getattr(response, "missing_fields", None)
        if missing_fields:
            return FallbackTrigger.MISSING_FIELD

    return None


class ModelPoolManager:
    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        pools: Optional[dict[str, Any]] = None,
        client_factory: Optional[ModelClientFactory] = None,
        failure_threshold: Optional[int] = None,
        failure_ttl_seconds: Optional[int] = None,
        max_attempts: Optional[int] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.pools = pools or dict(self.settings.model_pools or {})
        self.factory = client_factory or ModelClientFactory(self.settings)
        self.failure_threshold = (
            int(failure_threshold)
            if failure_threshold is not None
            else int(self.settings.model_failure_threshold)
        )
        self.failure_ttl_seconds = (
            int(failure_ttl_seconds)
            if failure_ttl_seconds is not None
            else int(self.settings.model_failure_ttl_seconds)
        )
        self.max_attempts = (
            int(max_attempts) if max_attempts is not None else int(self.settings.model_fallback_attempts)
        )
        self._failures: dict[str, int] = defaultdict(int)
        self._last_failure: dict[str, float] = {}
        self._usage_counts: dict[str, int] = defaultdict(int)

    def get_model(
        self,
        role: str | ModelRole,
        product_type: Optional[str] = None,
        preferred_model: Optional[str] = None,
        required_capabilities: Optional[list[str]] = None,
    ) -> ModelSelection:
        candidates = self._get_candidate_models(role, product_type, preferred_model, required_capabilities)
        if not candidates:
            raise ModelExhaustedError(f"No models configured for role: {role}")

        last_error: Optional[Exception] = None
        for model_id in candidates:
            if self._is_blocked(model_id):
                continue
            try:
                client = self.factory.create(model_id=model_id)
            except ModelClientFactoryError as exc:
                last_error = exc
                self.report_failure(model_id)
                logger.warning("Model client creation failed: %s", exc)
                continue
            self._usage_counts[model_id] += 1
            logger.info("Model selected: role=%s product_type=%s model=%s", role, product_type, model_id)
            return ModelSelection(model_id=model_id, client=client)

        if last_error is not None:
            raise ModelExhaustedError(f"No models available for role: {role}") from last_error
        raise ModelExhaustedError(f"No models available for role: {role}")

    async def run_with_fallback(
        self,
        *,
        role: str | ModelRole,
        product_type: Optional[str],
        preferred_model: Optional[str],
        call: Callable[[str, OpenAIClient], Awaitable[Any]],
        response_checker: Optional[Callable[[Any], Optional[FallbackTrigger]]] = None,
        max_attempts: Optional[int] = None,
        required_capabilities: Optional[list[str]] = None,
    ) -> ModelCallResult:
        candidates = self._get_candidate_models(role, product_type, preferred_model, required_capabilities)
        if not candidates:
            raise ModelExhaustedError(f"No models configured for role: {role}")

        attempts_limit = int(max_attempts) if max_attempts is not None else self.max_attempts
        attempts = 0
        last_error: Optional[Exception] = None

        for model_id in candidates:
            if attempts >= attempts_limit:
                break
            if self._is_blocked(model_id):
                continue
            attempts += 1
            try:
                client = self.factory.create(model_id=model_id)
            except ModelClientFactoryError as exc:
                last_error = exc
                self.report_failure(model_id)
                logger.warning("Model client creation failed: %s", exc)
                continue

            try:
                result = await call(model_id, client)
            except Exception as exc:
                trigger = should_fallback(exc, None, self._normalize_role(role))
                if trigger is None:
                    raise
                last_error = exc
                self.report_failure(model_id)
                logger.warning(
                    "Model call failed, triggering fallback: role=%s model=%s trigger=%s error=%s",
                    role,
                    model_id,
                    trigger.value,
                    exc,
                )
                continue

            trigger = should_fallback(None, result, self._normalize_role(role))
            if response_checker is not None:
                checker_trigger = response_checker(result)
                if checker_trigger is not None:
                    trigger = checker_trigger

            if trigger is not None:
                last_error = ModelSelectionError(f"Fallback triggered: {trigger.value}")
                self.report_failure(model_id)
                logger.warning(
                    "Model response triggered fallback: role=%s model=%s trigger=%s",
                    role,
                    model_id,
                    trigger.value,
                )
                continue

            self.reset_failure_count(model_id)
            self._usage_counts[model_id] += 1
            logger.info("Model call succeeded: role=%s product_type=%s model=%s", role, product_type, model_id)
            return ModelCallResult(model_id=model_id, result=result)

        if last_error is not None:
            raise ModelExhaustedError(f"No models available for role: {role}") from last_error
        raise ModelExhaustedError(f"No models available for role: {role}")

    def report_failure(self, model_id: str) -> None:
        self._failures[model_id] += 1
        self._last_failure[model_id] = time.time()

    def reset_failure_count(self, model_id: str) -> None:
        if model_id in self._failures:
            self._failures[model_id] = 0
        if model_id in self._last_failure:
            self._last_failure.pop(model_id, None)

    def get_usage_counts(self) -> dict[str, int]:
        return dict(self._usage_counts)

    def model_supports(self, model_id: str, capability: str) -> bool:
        return model_supports_capability(model_id, capability)

    def get_candidate_model_ids(
        self,
        role: str | ModelRole,
        product_type: Optional[str] = None,
        preferred_model: Optional[str] = None,
        required_capabilities: Optional[list[str]] = None,
    ) -> list[str]:
        return self._get_candidate_models(role, product_type, preferred_model, required_capabilities)

    def _get_candidate_models(
        self,
        role: str | ModelRole,
        product_type: Optional[str],
        preferred_model: Optional[str],
        required_capabilities: Optional[list[str]],
    ) -> list[str]:
        normalized_role = self._normalize_role(role)
        pools = self.pools.get(normalized_role)
        candidates: list[str] = []

        if isinstance(pools, dict):
            key = (product_type or "").lower().strip()
            selected = pools.get(key) or pools.get("default") or []
            candidates.extend(self._coerce_model_list(selected))
        else:
            candidates.extend(self._coerce_model_list(pools))

        if preferred_model:
            candidates.insert(0, preferred_model)

        role_override = self._resolve_role_override(normalized_role)
        if role_override:
            candidates.insert(0, role_override)

        resolved = []
        seen = set()
        for entry in candidates:
            model_id = self._resolve_model_id(entry)
            if not model_id or model_id in seen:
                continue
            seen.add(model_id)
            resolved.append(model_id)

        if required_capabilities:
            resolved = self._filter_by_capability(resolved, required_capabilities)
            if not resolved:
                return []

        if not resolved:
            resolved.append(self.settings.model)
        return resolved

    def _filter_by_capability(self, candidates: list[str], required_capabilities: list[str]) -> list[str]:
        required = [cap.lower().strip() for cap in required_capabilities if cap and str(cap).strip()]
        if not required:
            return candidates
        filtered: list[str] = []
        for model_id in candidates:
            if all(self.model_supports(model_id, cap) for cap in required):
                filtered.append(model_id)
        if not filtered:
            logger.warning("No models support required capabilities: %s", ", ".join(required))
        return filtered

    def _resolve_role_override(self, role: str) -> Optional[str]:
        if role == ModelRole.CLASSIFIER.value:
            return self.settings.model_classifier
        if role == ModelRole.WRITER.value:
            return self.settings.model_writer
        if role == ModelRole.EXPANDER.value:
            return self.settings.model_expander
        if role == ModelRole.VALIDATOR.value:
            return self.settings.model_validator
        if role == ModelRole.STYLE_REFINER.value:
            return self.settings.model_style_refiner
        return None

    def _resolve_model_id(self, value: Any) -> str:
        if not value:
            return ""
        text = str(value).strip()
        if not text:
            return ""
        aliases = get_model_aliases(self.settings)
        lowered = text.lower()
        return aliases.get(lowered, text)

    def _coerce_model_list(self, value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value if str(item).strip()]
        return [str(value)]

    def _normalize_role(self, role: str | ModelRole) -> str:
        if isinstance(role, ModelRole):
            return role.value
        return str(role).strip().lower()

    def _is_blocked(self, model_id: str) -> bool:
        failures = self._failures.get(model_id, 0)
        if failures < self.failure_threshold:
            return False
        last_failure = self._last_failure.get(model_id)
        if not last_failure:
            return False
        if time.time() - last_failure > self.failure_ttl_seconds:
            self.reset_failure_count(model_id)
            return False
        return True


_DEFAULT_POOL: ModelPoolManager | None = None


def get_model_pool_manager(settings: Optional[Settings] = None) -> ModelPoolManager:
    global _DEFAULT_POOL
    resolved = settings or get_settings()
    if _DEFAULT_POOL is None or _DEFAULT_POOL.settings is not resolved:
        _DEFAULT_POOL = ModelPoolManager(settings=resolved)
    return _DEFAULT_POOL


__all__ = [
    "FallbackTrigger",
    "ModelCallResult",
    "ModelExhaustedError",
    "ModelPoolManager",
    "ModelRole",
    "ModelSelection",
    "get_model_pool_manager",
    "should_fallback",
]
