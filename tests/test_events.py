from dashboard_service.events import ClientRole, DashboardEvent, EventBuffer, EventStatus


def test_viewer_payload_redacts_developer_detail() -> None:
    event = DashboardEvent(
        event_type="span_start",
        status=EventStatus.ACTIVE,
        trace_id="trace_123456789abcdef",
        span_id="span_123456789abcdef",
        session_id="raw-session-id",
        summary="Tool running",
        metadata={"raw": "hidden"},
        detail={"prompt": "hidden"},
    )

    payload = event.to_client_payload(ClientRole.VIEWER)

    assert payload["trace_id"] == "trace_123456"
    assert payload["span_id"] == "span_1234567"
    assert payload["session_id"].startswith("session-")
    assert payload["metadata"] == {}
    assert "detail" not in payload


def test_developer_payload_keeps_detail() -> None:
    event = DashboardEvent(
        event_type="span_end",
        status=EventStatus.SUCCESS,
        detail={"tokens": 123},
    )

    payload = event.to_client_payload(ClientRole.DEVELOPER)

    assert payload["detail"] == {"tokens": 123}


def test_event_buffer_respects_max_length() -> None:
    buffer = EventBuffer(maxlen=2)
    buffer.add(DashboardEvent(event_type="one"))
    buffer.add(DashboardEvent(event_type="two"))
    buffer.add(DashboardEvent(event_type="three"))

    snapshot = buffer.snapshot(ClientRole.DEVELOPER)

    assert [event["event_type"] for event in snapshot] == ["two", "three"]
