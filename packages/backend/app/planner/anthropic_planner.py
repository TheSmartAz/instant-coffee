from __future__ import annotations

import logging
from typing import Optional

import httpx

from ..config import get_settings
from .base import (
    BasePlanner,
    Plan,
    PlannerAPIError,
    PlannerError,
    PlannerRateLimitError,
    PlannerResponseError,
)
from .prompts import PLANNER_SYSTEM_PROMPT, PLANNER_USER_PROMPT

logger = logging.getLogger(__name__)


class AnthropicPlanner(BasePlanner):
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        api_version: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model or settings.planner_model
        self.base_url = base_url or settings.anthropic_base_url
        self.api_version = api_version or settings.anthropic_api_version
        timeout = timeout_seconds or settings.planner_timeout_seconds
        if not self.api_key:
            raise PlannerError("ANTHROPIC_API_KEY is not configured")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def plan(self, user_message: str, context: Optional[str] = None) -> Plan:
        context_str = f"上下文: {context}" if context else ""
        user_prompt = PLANNER_USER_PROMPT.format(
            user_message=user_message,
            context=context_str,
        )
        payload = {
            "model": self.model,
            "max_tokens": 1200,
            "temperature": 0.7,
            "system": PLANNER_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "content-type": "application/json",
        }

        response_json = await self._call_with_retry(payload=payload, headers=headers)
        content = self._extract_content(response_json)
        data = self._extract_json(content)
        if not data:
            raise PlannerResponseError("Anthropic response did not include valid JSON")
        return self._build_plan(data, user_message)

    async def _call_with_retry(self, *, payload: dict, headers: dict) -> dict:
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await self._call_once(payload=payload, headers=headers)
            except PlannerRateLimitError as exc:  # pragma: no cover - depends on API
                last_error = exc
                await self._backoff(attempt, "rate limit")
            except PlannerAPIError as exc:  # pragma: no cover - depends on API
                last_error = exc
                await self._backoff(attempt, "api error")
        if last_error is None:
            raise PlannerError("Unknown planner error")
        raise PlannerError(str(last_error))

    async def _call_once(self, *, payload: dict, headers: dict) -> dict:
        response = await self._client.post("/v1/messages", json=payload, headers=headers)
        if response.status_code == 429:
            raise PlannerRateLimitError(response.text)
        if response.status_code >= 500:
            raise PlannerAPIError(response.text)
        if response.status_code >= 400:
            raise PlannerError(
                f"Anthropic API error {response.status_code}: {response.text}"
            )
        return response.json()

    def _extract_content(self, response_json: dict) -> str:
        if isinstance(response_json, dict):
            content_list = response_json.get("content") or []
            for item in content_list:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text")
                    if text:
                        return str(text).strip()
        return ""


__all__ = ["AnthropicPlanner"]
