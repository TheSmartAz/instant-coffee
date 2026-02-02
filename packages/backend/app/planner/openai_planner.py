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


class OpenAIPlanner(BasePlanner):
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.planner_model
        self.base_url = base_url or settings.openai_base_url
        self.api_mode = getattr(settings, "openai_api_mode", "responses") or "responses"
        timeout = timeout_seconds or settings.planner_timeout_seconds
        if not self.api_key:
            raise PlannerError("OPENAI_API_KEY is not configured")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def plan(self, user_message: str, context: Optional[str] = None) -> Plan:
        context_str = f"Context: {context}" if context else ""
        user_prompt = PLANNER_USER_PROMPT.format(
            user_message=user_message,
            context=context_str,
        )
        if self._use_chat_completions():
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
            }
            endpoint = "/chat/completions"
        else:
            payload = {
                "model": self.model,
                "input": [
                    {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
            }
            endpoint = "/responses"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response_json = await self._call_with_retry(payload=payload, headers=headers, endpoint=endpoint)
        content = self._extract_content(response_json)
        data = self._extract_json(content)
        if not data:
            raise PlannerResponseError("OpenAI response did not include valid JSON")
        return self._build_plan(data, user_message)

    def _use_chat_completions(self) -> bool:
        normalized = str(self.api_mode).strip().lower()
        return normalized in {"chat", "chat_completions", "chat-completions", "completions"}

    async def _call_with_retry(self, *, payload: dict, headers: dict, endpoint: str) -> dict:
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await self._call_once(payload=payload, headers=headers, endpoint=endpoint)
            except PlannerRateLimitError as exc:  # pragma: no cover - depends on API
                last_error = exc
                await self._backoff(attempt, "rate limit")
            except PlannerAPIError as exc:  # pragma: no cover - depends on API
                last_error = exc
                await self._backoff(attempt, "api error")
        if last_error is None:
            raise PlannerError("Unknown planner error")
        raise PlannerError(str(last_error))

    async def _call_once(self, *, payload: dict, headers: dict, endpoint: str) -> dict:
        response = await self._client.post(endpoint, json=payload, headers=headers)
        if response.status_code == 429:
            raise PlannerRateLimitError(response.text)
        if response.status_code >= 500:
            raise PlannerAPIError(response.text)
        if response.status_code >= 400:
            raise PlannerError(f"OpenAI API error {response.status_code}: {response.text}")
        return response.json()

    def _extract_content(self, response_json: dict) -> str:
        if not isinstance(response_json, dict):
            return ""
        if self._use_chat_completions():
            choices = response_json.get("choices") or []
            if choices:
                message = choices[0].get("message") or {}
                content = message.get("content")
                if content:
                    return str(content).strip()
            return ""

        output_text = response_json.get("output_text")
        if output_text:
            return str(output_text).strip()
        output_items = response_json.get("output") or []
        for item in output_items:
            if item.get("type") != "message":
                continue
            for content in item.get("content") or []:
                if content.get("type") in {"output_text", "text"}:
                    text = content.get("text") or content.get("value")
                    if text:
                        return str(text).strip()
        return ""


__all__ = ["OpenAIPlanner"]
