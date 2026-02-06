from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy.orm import Session as DbSession

from ..utils.datetime import utcnow
from ..db.models import Session as SessionModel
from ..schemas.session_metadata import (
    BuildInfo,
    BuildStatus,
    SessionMetadata,
    SessionMetadataUpdate,
)


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return value.value
    return str(value)


def _normalize_json(payload: Any) -> Any:
    if payload is None:
        return None
    try:
        json.dumps(payload, ensure_ascii=False, default=_json_default)
        return payload
    except TypeError:
        return json.loads(json.dumps(payload, ensure_ascii=False, default=_json_default))


def _normalize_build_status(status: BuildStatus | str | None) -> BuildStatus:
    if status is None:
        return BuildStatus.PENDING
    if isinstance(status, BuildStatus):
        return status
    try:
        return BuildStatus(str(status))
    except ValueError as exc:
        raise ValueError(f"Invalid build status: {status}") from exc


class StateStoreService:
    """Persist and retrieve graph state + build metadata on sessions."""

    def __init__(self, db: DbSession) -> None:
        self.db = db

    def save_state(self, session_id: str, state: dict) -> bool:
        if state is not None and not isinstance(state, dict):
            raise ValueError("Graph state must be a dictionary")
        payload = _normalize_json(state)
        return self._update_fields(session_id, graph_state=payload)

    def load_state(self, session_id: str) -> Optional[dict]:
        record = self.db.get(SessionModel, session_id)
        if record is None:
            return None
        state = record.graph_state
        return state if isinstance(state, dict) else None

    def clear_state(self, session_id: str) -> bool:
        return self._update_fields(session_id, graph_state=None)

    def get_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        record = self.db.get(SessionModel, session_id)
        if record is None:
            return None
        return self._to_metadata(record)

    def update_metadata(
        self,
        session_id: str,
        updates: SessionMetadataUpdate | dict[str, Any],
    ) -> Optional[SessionMetadata]:
        payload: dict[str, Any]
        if isinstance(updates, SessionMetadataUpdate):
            payload = updates.model_dump(mode="json", exclude_none=True, exclude_unset=True)
        elif isinstance(updates, dict):
            payload = {key: value for key, value in updates.items() if value is not None}
        else:
            raise ValueError("Updates must be a SessionMetadataUpdate or dict")

        if "graph_state" in payload and payload["graph_state"] is not None:
            if not isinstance(payload["graph_state"], dict):
                raise ValueError("Graph state must be a dictionary")
            payload["graph_state"] = _normalize_json(payload["graph_state"])
        if "build_status" in payload:
            payload["build_status"] = _normalize_build_status(payload["build_status"]).value
        if "build_artifacts" in payload:
            payload["build_artifacts"] = _normalize_json(payload["build_artifacts"])
        if "aesthetic_scores" in payload:
            payload["aesthetic_scores"] = _normalize_json(payload["aesthetic_scores"])

        record = self._update_fields(session_id, return_record=True, **payload)
        return self._to_metadata(record) if record is not None else None

    def update_build_status(
        self,
        session_id: str,
        status: BuildStatus | str,
        *,
        build_artifacts: Optional[dict[str, Any]] = None,
    ) -> bool:
        resolved_status = _normalize_build_status(status).value
        updates: dict[str, Any] = {"build_status": resolved_status}
        if build_artifacts is not None:
            updates["build_artifacts"] = _normalize_json(build_artifacts)
        return self._update_fields(session_id, **updates)

    def update_build_info(self, session_id: str, info: BuildInfo) -> bool:
        payload = info.model_dump(mode="json", exclude_none=True, exclude_unset=True)
        return self._update_fields(
            session_id,
            build_status=_normalize_build_status(info.status).value,
            build_artifacts=_normalize_json(payload),
        )

    def update_aesthetic_scores(self, session_id: str, scores: dict[str, Any]) -> bool:
        if scores is not None and not isinstance(scores, dict):
            raise ValueError("Aesthetic scores must be a dictionary")
        return self._update_fields(session_id, aesthetic_scores=_normalize_json(scores))

    def clear_metadata(self, session_id: str) -> bool:
        return self._update_fields(
            session_id,
            graph_state=None,
            build_status=BuildStatus.PENDING.value,
            build_artifacts=None,
            aesthetic_scores=None,
        )

    def _update_fields(
        self,
        session_id: str,
        return_record: bool = False,
        **fields: Any,
    ) -> bool | SessionModel | None:
        record = self.db.get(SessionModel, session_id)
        if record is None:
            return None if return_record else False
        if not fields:
            return record if return_record else True
        for key, value in fields.items():
            if not hasattr(record, key):
                continue
            setattr(record, key, value)
        record.updated_at = utcnow()
        self.db.add(record)
        self.db.flush()
        return record if return_record else True

    @staticmethod
    def _to_metadata(record: SessionModel) -> SessionMetadata:
        build_status = record.build_status or BuildStatus.PENDING.value
        try:
            status = BuildStatus(build_status)
        except ValueError:
            status = BuildStatus.PENDING
        return SessionMetadata(
            session_id=record.id,
            graph_state=record.graph_state,
            build_status=status,
            build_artifacts=record.build_artifacts,
            aesthetic_scores=record.aesthetic_scores,
            updated_at=record.updated_at,
        )


__all__ = ["StateStoreService"]
