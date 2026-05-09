from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ClientRole(StrEnum):
    VIEWER = "viewer"
    DEVELOPER = "developer"


class EventStatus(StrEnum):
    ACTIVE = "active"
    SUCCESS = "success"
    ERROR = "error"
    IDLE = "idle"
    UNKNOWN = "unknown"


class DashboardEvent(BaseModel):
    """Normalized trace event used by the dashboard."""

    model_config = ConfigDict(extra="allow")

    event_id: str = Field(default_factory=lambda: uuid4().hex)
    event_type: str
    status: EventStatus = EventStatus.UNKNOWN
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    session_id: str | None = None
    node_id: str | None = None
    agent_id: str | None = None
    tool_name: str | None = None
    span_type: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    summary: str | None = None
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    detail: dict[str, Any] = Field(default_factory=dict)

    def to_client_payload(self, role: ClientRole) -> dict[str, Any]:
        payload = self.model_dump(mode="json")

        if role is ClientRole.DEVELOPER:
            return payload

        payload["trace_id"] = _short_identifier(self.trace_id)
        payload["span_id"] = _short_identifier(self.span_id)
        payload["parent_span_id"] = _short_identifier(self.parent_span_id)
        payload["session_id"] = _pseudonymize(self.session_id)
        payload["metadata"] = _viewer_metadata(self.metadata)
        payload.pop("detail", None)
        return payload


class EventBuffer:
    """Fixed-size replay buffer for recent dashboard events."""

    def __init__(self, maxlen: int) -> None:
        self._events: deque[DashboardEvent] = deque(maxlen=maxlen)

    def add(self, event: DashboardEvent) -> None:
        self._events.append(event)

    def extend(self, events: Iterable[DashboardEvent]) -> None:
        for event in events:
            self.add(event)

    def snapshot(self, role: ClientRole) -> list[dict[str, Any]]:
        return [event.to_client_payload(role) for event in self._events]

    def __len__(self) -> int:
        return len(self._events)


def event_from_mapping(payload: dict[str, Any]) -> DashboardEvent:
    raw_status = payload.get("status")
    if raw_status is None:
        event_type = str(payload.get("event_type", "status"))
        raw_status = _status_from_event_type(event_type)

    return DashboardEvent(
        event_type=str(payload.get("event_type", "status")),
        status=_coerce_status(raw_status),
        timestamp=payload.get("timestamp") or datetime.now(UTC),
        trace_id=_optional_string(payload.get("trace_id")),
        span_id=_optional_string(payload.get("span_id")),
        parent_span_id=_optional_string(payload.get("parent_span_id")),
        session_id=_optional_string(payload.get("session_id")),
        node_id=_optional_string(payload.get("node_id")),
        agent_id=_optional_string(payload.get("agent_id")),
        tool_name=_optional_string(payload.get("tool_name")),
        span_type=_optional_string(payload.get("span_type")),
        duration_ms=payload.get("duration_ms"),
        summary=_optional_string(payload.get("summary")),
        message=_optional_string(payload.get("message")),
        metadata=_dict_or_empty(payload.get("metadata")),
        detail=_dict_or_empty(payload.get("detail")),
    )


def resolve_role(
    token: str | None,
    viewer_token: str,
    developer_token: str | None,
) -> ClientRole | None:
    if token is None:
        return None
    if developer_token is not None and token == developer_token:
        return ClientRole.DEVELOPER
    if token == viewer_token:
        return ClientRole.VIEWER
    return None


def _status_from_event_type(event_type: str) -> Literal["active", "success", "error", "unknown"]:
    if event_type.endswith("_start"):
        return "active"
    if event_type.endswith("_end"):
        return "success"
    if "error" in event_type:
        return "error"
    return "unknown"


def _coerce_status(value: object) -> EventStatus:
    try:
        return EventStatus(str(value))
    except ValueError:
        return EventStatus.UNKNOWN


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dict_or_empty(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _short_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    return value[:12]


def _pseudonymize(value: str | None) -> str | None:
    if value is None:
        return None
    digest = sha256(value.encode("utf-8")).hexdigest()
    return f"session-{digest[:10]}"


def _viewer_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    safe_keys = {
        "workflow_name",
        "span_data_type",
        "name",
        "sdk_span_type",
        "task_name",
        "turn",
        "agent_name",
        "from_agent",
        "to_agent",
        "model",
        "server",
        "triggered",
        "tools",
        "handoffs",
    }
    return {key: value for key, value in metadata.items() if key in safe_keys}
