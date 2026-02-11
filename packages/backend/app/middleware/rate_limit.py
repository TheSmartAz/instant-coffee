"""Simple in-memory rate limiting middleware for FastAPI."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket rate limiter keyed by client IP.

    Args:
        app: The ASGI application.
        default_rpm: Default requests per minute for all endpoints.
        expensive_rpm: Rate limit for expensive endpoints (chat, build).
        expensive_prefixes: URL prefixes considered expensive.
    """

    def __init__(
        self,
        app,
        default_rpm: int = 120,
        expensive_rpm: int = 30,
        expensive_prefixes: tuple[str, ...] = (
            "/api/chat",
            "/api/sessions/",
        ),
    ):
        super().__init__(app)
        self.default_rpm = default_rpm
        self.expensive_rpm = expensive_rpm
        self.expensive_prefixes = expensive_prefixes
        # {(ip, bucket_key): (tokens, last_refill_time)}
        self._buckets: dict[tuple[str, str], list] = defaultdict(
            lambda: [0.0, 0.0]
        )

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _is_expensive(self, path: str, method: str) -> bool:
        if method == "GET":
            return False
        return any(path.startswith(prefix) for prefix in self.expensive_prefixes)

    def _check_rate(self, ip: str, bucket_key: str, rpm: int) -> bool:
        """Return True if request is allowed, False if rate limited."""
        now = time.monotonic()
        key = (ip, bucket_key)
        bucket = self._buckets[key]
        # bucket[0] = tokens, bucket[1] = last_refill_time
        if bucket[1] == 0.0:
            bucket[0] = float(rpm)
            bucket[1] = now

        elapsed = now - bucket[1]
        bucket[1] = now
        bucket[0] = min(float(rpm), bucket[0] + elapsed * (rpm / 60.0))

        if bucket[0] >= 1.0:
            bucket[0] -= 1.0
            return True
        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip health check and static assets
        path = request.url.path
        if path in ("/health", "/docs", "/openapi.json") or path.startswith("/assets"):
            return await call_next(request)

        ip = self._get_client_ip(request)
        is_expensive = self._is_expensive(path, request.method)
        rpm = self.expensive_rpm if is_expensive else self.default_rpm
        bucket_key = "expensive" if is_expensive else "default"

        if not self._check_rate(ip, bucket_key, rpm):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please slow down.",
                    "retry_after_seconds": 60 // rpm,
                },
                headers={"Retry-After": str(60 // rpm)},
            )

        return await call_next(request)
