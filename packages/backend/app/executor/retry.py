from __future__ import annotations

from dataclasses import dataclass


class TemporaryError(Exception):
    """Temporary error that can be retried."""


@dataclass
class RetryPolicy:
    max_retries: int = 3
    base_delay: float = 1.0
    multiplier: float = 2.0

    def get_delay(self, attempt: int) -> float:
        return self.base_delay * (self.multiplier ** (attempt - 1))


__all__ = ["TemporaryError", "RetryPolicy"]
