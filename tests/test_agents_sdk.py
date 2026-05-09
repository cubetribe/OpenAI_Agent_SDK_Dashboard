from dataclasses import dataclass
from datetime import UTC, datetime

from dashboard_service.agents_sdk import AgentsDashboardTraceProcessor
from dashboard_service.events import DashboardEvent, EventStatus


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[DashboardEvent] = []
        self.closed = False

    def publish(self, event: DashboardEvent) -> None:
        self.events.append(event)

    def close(self) -> None:
        self.closed = True


@dataclass
class FakeTrace:
    trace_id: str
    workflow_name: str
    group_id: str
    metadata: dict[str, str]
    started_at: datetime
    ended_at: datetime | None = None


@dataclass
class AgentSpanData:
    name: str
    type: str = "agent"


@dataclass
class FunctionSpanData:
    name: str
    type: str = "function"
    input: str = "hidden unless detail is enabled"


class ExportedAgentSpanData:
    def __init__(self, name: str) -> None:
        self.name = name

    def export(self) -> dict[str, str]:
        return {"type": "agent", "name": self.name}


class ExportedTurnSpanData:
    def export(self) -> dict[str, object]:
        return {
            "type": "custom",
            "name": "turn",
            "data": {
                "sdk_span_type": "turn",
                "turn": 2,
                "agent_name": "Example Agents SDK",
            },
        }


class ExportedGenerationSpanData:
    def export(self) -> dict[str, object]:
        return {
            "type": "generation",
            "model": "gpt-test",
            "usage": {"input_tokens": 10, "output_tokens": 4},
        }


@dataclass
class FakeSpan:
    span_id: str
    trace_id: str
    parent_id: str | None
    span_data: object
    started_at: datetime
    ended_at: datetime | None = None
    error: str | None = None


def test_trace_processor_publishes_trace_lifecycle() -> None:
    publisher = RecordingPublisher()
    processor = AgentsDashboardTraceProcessor(publisher=publisher)
    trace = FakeTrace(
        trace_id="trace_123",
        workflow_name="Support workflow",
        group_id="group-1",
        metadata={"session_id": "session-1"},
        started_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
        ended_at=datetime(2026, 5, 8, 10, 1, tzinfo=UTC),
    )

    processor.on_trace_start(trace)
    processor.on_trace_end(trace)

    assert [event.event_type for event in publisher.events] == ["trace_start", "trace_end"]
    assert publisher.events[0].session_id == "session-1"
    assert publisher.events[0].summary == "Support workflow started"
    assert publisher.events[1].status is EventStatus.SUCCESS


def test_trace_processor_maps_agent_span() -> None:
    publisher = RecordingPublisher()
    processor = AgentsDashboardTraceProcessor(publisher=publisher)
    span = FakeSpan(
        span_id="span_123",
        trace_id="trace_123",
        parent_id=None,
        span_data=AgentSpanData(name="orchestrator"),
        started_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
    )

    processor.on_span_start(span)

    event = publisher.events[0]
    assert event.event_type == "span_start"
    assert event.agent_id == "orchestrator"
    assert event.span_type == "agent"
    assert event.detail == {}


def test_trace_processor_maps_exported_agent_span_data() -> None:
    publisher = RecordingPublisher()
    processor = AgentsDashboardTraceProcessor(publisher=publisher)
    span = FakeSpan(
        span_id="span_123",
        trace_id="trace_123",
        parent_id=None,
        span_data=ExportedAgentSpanData(name="Example Agents SDK"),
        started_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
    )

    processor.on_span_start(span)

    event = publisher.events[0]
    assert event.agent_id == "Example Agents SDK"
    assert event.span_type == "agent"


def test_trace_processor_maps_exported_turn_span_data() -> None:
    publisher = RecordingPublisher()
    processor = AgentsDashboardTraceProcessor(publisher=publisher)
    span = FakeSpan(
        span_id="span_123",
        trace_id="trace_123",
        parent_id=None,
        span_data=ExportedTurnSpanData(),
        started_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
    )

    processor.on_span_start(span)

    event = publisher.events[0]
    assert event.agent_id == "Example Agents SDK"
    assert event.span_type == "turn"
    assert event.summary == "Example Agents SDK turn 2 started"
    assert event.metadata["sdk_span_type"] == "turn"
    assert event.metadata["turn"] == 2


def test_trace_processor_maps_exported_generation_span_data() -> None:
    publisher = RecordingPublisher()
    processor = AgentsDashboardTraceProcessor(publisher=publisher)
    span = FakeSpan(
        span_id="span_123",
        trace_id="trace_123",
        parent_id=None,
        span_data=ExportedGenerationSpanData(),
        started_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
    )

    processor.on_span_start(span)

    event = publisher.events[0]
    assert event.span_type == "generation"
    assert event.summary == "gpt-test started"
    assert event.metadata["model"] == "gpt-test"
    assert event.detail == {}


def test_trace_processor_maps_tool_span_error_with_detail() -> None:
    publisher = RecordingPublisher()
    processor = AgentsDashboardTraceProcessor(publisher=publisher, include_detail=True)
    span = FakeSpan(
        span_id="span_123",
        trace_id="trace_123",
        parent_id="span_parent",
        span_data=FunctionSpanData(name="lookup"),
        started_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
        ended_at=datetime(2026, 5, 8, 10, 0, 1, tzinfo=UTC),
        error="upstream timeout",
    )

    processor.on_span_end(span)

    event = publisher.events[0]
    assert event.status is EventStatus.ERROR
    assert event.tool_name == "lookup"
    assert event.duration_ms == 1000
    assert event.message == "upstream timeout"
    assert event.detail["span_data"]["input"] == "hidden unless detail is enabled"


def test_trace_processor_shutdown_closes_publisher() -> None:
    publisher = RecordingPublisher()
    processor = AgentsDashboardTraceProcessor(publisher=publisher)

    processor.shutdown()

    assert publisher.closed is True
