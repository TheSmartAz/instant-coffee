from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)


async def with_retry(
    func: Callable[..., Awaitable[Any]],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 1.0,
    retry_on: Optional[Tuple[Type[BaseException], ...]] = None,
    **kwargs: Any,
) -> Any:
    """
    Execute an async function with exponential backoff retry.

    Args:
        func: Async function to execute
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (doubles each retry)
        retry_on: Exception types that should be retried. If None, retry all.
    """
    attempts = max(1, int(max_retries))
    last_exception: Optional[BaseException] = None

    for attempt in range(1, attempts + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - depends on caller
            last_exception = exc
            if retry_on is not None and not isinstance(exc, retry_on):
                raise
            if attempt >= attempts:
                logger.error("All %s attempts failed: %s", attempts, exc)
                break
            delay = float(base_delay) * (2 ** (attempt - 1))
            logger.warning(
                "Attempt %s/%s failed: %s. Retrying in %.2fs...",
                attempt,
                attempts,
                exc,
                delay,
            )
            await asyncio.sleep(delay)

    if last_exception is None:
        raise RuntimeError("Retry failed without capturing an exception")
    raise last_exception
