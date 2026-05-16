from __future__ import annotations

import secrets

from fastapi import Header, HTTPException

from ..config import get_settings


def require_admin_token(
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
) -> None:
    """Require an admin token unless an explicit unsafe dev bypass is enabled."""
    settings = get_settings()
    expected = (settings.admin_token or "").strip()
    if not expected:
        if settings.allow_unsafe_dev_admin_bypass:
            return
        raise HTTPException(status_code=401, detail="Admin token is not configured")

    bearer_token = None
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value.strip():
            bearer_token = value.strip()

    provided = (x_admin_token or "").strip() or bearer_token
    if provided and secrets.compare_digest(provided, expected):
        return

    raise HTTPException(status_code=401, detail="Admin token required")


__all__ = ["require_admin_token"]
