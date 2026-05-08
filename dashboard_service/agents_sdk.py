from __future__ import annotations

import dataclasses
import importlib
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

from dashboard_service.events import DashboardEvent, EventStatus
from dashboard_service.publisher import DashboardEventPublisher, RedisDashboardPublisher


class AgentsDashboardTraceProcessor:
    """OpenAI Agents SDK tracing processor that emits normalized dashboard events."""

    def __init__(
        self,
        publisher: DashboardEventPublisher,
        *,
        include_detail: bool = False,
        session_metadata_keys: tuple[str, ...] = ("session_id", "conversation_id", "thread_id"),
    ) -> None:
        self.publisher = publisher
        self.include_detail = include_detail
        self.session_metadata_keys = session_metadata_keys

    @classmethod
    def from_env(cls) -> AgentsDashboardTraceProcessor:
        include_detail = os.environ.get("DASHBOARD_TRACE_INCLUDE_DETAIL", "").lower() in {
            "1",
            "true",
            "yes",
        }
        return cls(
            publisher=RedisDashboardPublisher.from_env(),
            include_detail=include_detail,
        )

    def on_trace_start(self, trace: object) -> None:
        self.publisher.publish(self._trace_event(trace, "trace_start", EventStatus.ACTIVE))

    def on_trace_end(self, trace: object) -> None:
        self.publisher.publish(self._trace_event(trace, "trace_end", EventStatus.SUCCESS))

    def on_span_start(self, span: object) -> None:
        self.publisher.publish(self._span_event(span, "span_start", EventStatus.ACTIVE))

    def on_span_end(self, span: object) -> None:
        status = EventStatus.ERROR if _extract_error(span) is not None else EventStatus.SUCCESS
        self.publisher.publish(self._span_event(span, "span_end", status))

    def shutdown(self) -> None:
        self.publisher.close()

    def force_flush(self) -> None:
        return None

    def _trace_event(self, trace: object, event_type: str, status: EventStatus) -> DashboardEvent:
        metadata = _safe_mapping(_getattr(trace, "metadata"))
        workflow_name = _string(_getattr(trace, "workflow_name") or _getattr(trace, "name"))
        session_id = _session_id_from_trace(trace, metadata, self.session_metadata_keys)

        detail: dict[str, Any] = {}
        if self.include_detail:
            detail = {
                "trace": _json_safe(_object_mapping(trace)),
            }

        return DashboardEvent(
            event_type=event_type,
            status=status,
            timestamp=_timestamp_from_object(trace, "started_at", "ended_at"),
            trace_id=_string(_getattr(trace, "trace_id")),
            session_id=session_id,
            summary=_summary(event_type, workflow_name),
            metadata={
                "workflow_name": workflow_name,
                "group_id": _string(_getattr(trace, "group_id")),
            },
            detail=detail,
        )

    def _span_event(self, span: object, event_type: str, status: EventStatus) -> DashboardEvent:
        span_data = _span_data_mapping(span)
        span_type = _span_type(span_data)
        agent_id = _agent_id(span_data, span_type)
        tool_name = _tool_name(span_data, span_type)
        error = _extract_error(span)

        detail: dict[str, Any] = {}
        if self.include_detail:
            detail = {
                "span": _json_safe(_object_mapping(span)),
                "span_data": _json_safe(span_data),
                "error": _json_safe(error),
            }

        return DashboardEvent(
            event_type=event_type,
            status=status,
            timestamp=_timestamp_from_object(span, "started_at", "ended_at"),
            trace_id=_string(_getattr(span, "trace_id")),
            span_id=_string(_getattr(span, "span_id")),
            parent_span_id=_string(_getattr(span, "parent_id")),
            node_id=_string(span_data.get("dashboard_node_id")),
            agent_id=agent_id,
            tool_name=tool_name,
            span_type=span_type,
            duration_ms=_duration_ms(span),
            summary=_summary(event_type, agent_id or tool_name or span_type),
            message=_string(error),
            metadata={
                "span_data_type": span_type,
                "name": _string(span_data.get("name")),
            },
            detail=detail,
        )


def register_dashboard_trace_processor(
    processor: AgentsDashboardTraceProcessor | None = None,
) -> AgentsDashboardTraceProcessor:
    """Register the dashboard processor with the OpenAI Agents SDK.

    The helper intentionally imports the SDK lazily so the dashboard service can run without the
    Agents SDK installed. Upstream agent applications should call this during startup.
    """

    trace_processor = processor or AgentsDashboardTraceProcessor.from_env()
    add_trace_processor = _load_add_trace_processor()
    add_trace_processor(trace_processor)
    return trace_processor


def _load_add_trace_processor() -> Callable[[object], None]:
    try:
        tracing_module: Any = importlib.import_module("agents.tracing")
    except ImportError:
        tracing_module = importlib.import_module("agents")

    add_trace_processor = tracing_module.add_trace_processor
    if not callable(add_trace_processor):
        msg = "OpenAI Agents SDK does not expose add_trace_processor."
        raise RuntimeError(msg)
    return cast(Callable[[object], None], add_trace_processor)


def _span_data_mapping(span: object) -> dict[str, Any]:
    return _object_mapping(_getattr(span, "span_data") or _getattr(span, "data"))


def _span_type(span_data: dict[str, Any]) -> str | None:
    explicit_type = _string(span_data.get("type") or span_data.get("span_type"))
    if explicit_type is not None:
        return explicit_type

    raw_class_name = _string(span_data.get("__class__"))
    if raw_class_name is None:
        return None

    class_name = raw_class_name.removesuffix("SpanData")
    return _camel_to_snake(class_name).replace("_span", "")


def _agent_id(span_data: dict[str, Any], span_type: str | None) -> str | None:
    if span_type == "agent":
        return _string(span_data.get("name"))
    return _string(
        span_data.get("agent_id") or span_data.get("agent_name") or span_data.get("agent")
    )


def _tool_name(span_data: dict[str, Any], span_type: str | None) -> str | None:
    if span_type in {"function", "tool"}:
        return _string(span_data.get("name"))
    return _string(span_data.get("tool_name") or span_data.get("function_name"))


def _extract_error(item: object) -> object | None:
    return _getattr(item, "error")


def _session_id_from_trace(
    trace: object,
    metadata: dict[str, Any],
    metadata_keys: tuple[str, ...],
) -> str | None:
    for key in metadata_keys:
        session_id = _string(metadata.get(key))
        if session_id is not None:
            return session_id
    return _string(_getattr(trace, "group_id"))


def _timestamp_from_object(item: object, start_attr: str, end_attr: str) -> datetime:
    timestamp = _parse_datetime(_getattr(item, end_attr)) or _parse_datetime(
        _getattr(item, start_attr)
    )
    return timestamp or datetime.now(UTC)


def _duration_ms(item: object) -> int | None:
    started_at = _parse_datetime(_getattr(item, "started_at"))
    ended_at = _parse_datetime(_getattr(item, "ended_at"))
    if started_at is None or ended_at is None:
        return None
    duration = ended_at - started_at
    return max(0, int(duration.total_seconds() * 1000))


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    if not isinstance(value, str):
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _summary(event_type: str, label: str | None) -> str:
    normalized_label = label or "workflow"
    if event_type.endswith("_start"):
        return f"{normalized_label} started"
    if event_type.endswith("_end"):
        return f"{normalized_label} finished"
    return normalized_label


def _object_mapping(item: object) -> dict[str, Any]:
    if item is None:
        return {}
    if dataclasses.is_dataclass(item) and not isinstance(item, type):
        return _safe_mapping(dataclasses.asdict(item))
    model_dump = getattr(item, "model_dump", None)
    if callable(model_dump):
        return _safe_mapping(model_dump())
    to_dict = getattr(item, "to_dict", None)
    if callable(to_dict):
        return _safe_mapping(to_dict())
    if isinstance(item, dict):
        return _safe_mapping(item)
    return _safe_mapping(vars(item)) if hasattr(item, "__dict__") else {}


def _safe_mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _json_safe(item) for key, item in value.items()}


def _json_safe(value: object) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_safe(item) for item in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _json_safe(dataclasses.asdict(value))
    return str(value)


def _getattr(item: object, name: str) -> object | None:
    return getattr(item, name, None)


def _string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _camel_to_snake(value: str) -> str:
    output: list[str] = []
    for index, char in enumerate(value):
        if char.isupper() and index > 0:
            output.append("_")
        output.append(char.lower())
    return "".join(output)
