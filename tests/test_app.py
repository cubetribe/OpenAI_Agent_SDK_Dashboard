import tempfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from dashboard_service.events import DashboardEvent, EventStatus
from dashboard_service.main import create_app
from dashboard_service.settings import Settings


def test_health_endpoint() -> None:
    client = TestClient(_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["dev_tools_enabled"] is False


def test_replay_requires_token() -> None:
    client = TestClient(_app())

    response = client.get("/api/events/replay")

    assert response.status_code == 401


def test_replay_uses_viewer_redaction() -> None:
    app = _app()
    app.state.event_buffer.add(
        DashboardEvent(
            event_type="span_start",
            status=EventStatus.ACTIVE,
            session_id="private-session",
            detail={"prompt": "hidden"},
        )
    )
    client = TestClient(app)

    response = client.get("/api/events/replay", headers={"Authorization": "Bearer viewer-token"})

    assert response.status_code == 200
    event = response.json()["events"][0]
    assert event["session_id"].startswith("session-")
    assert "detail" not in event


def test_replay_developer_role_keeps_detail() -> None:
    app = _app()
    app.state.event_buffer.add(
        DashboardEvent(
            event_type="span_start",
            status=EventStatus.ACTIVE,
            detail={"tokens": 10},
        )
    )
    client = TestClient(app)

    response = client.get(
        "/api/events/replay",
        headers={"Authorization": "Bearer developer-token"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "developer"
    assert response.json()["events"][0]["detail"] == {"tokens": 10}


def test_search_events_filters_errors_and_redacts_viewer_payload() -> None:
    app = _app()
    app.state.event_store.add(
        DashboardEvent(
            event_type="span_end",
            status=EventStatus.ERROR,
            node_id="node-tool",
            trace_id="trace_private_123456789",
            session_id="private-session",
            summary="Tool lookup failed",
            detail={"stack": "hidden"},
        )
    )
    app.state.event_store.add(
        DashboardEvent(
            event_type="span_end",
            status=EventStatus.SUCCESS,
            node_id="node-response",
            summary="Workflow completed",
        )
    )
    client = TestClient(app)

    response = client.get(
        "/api/events/search?status=error&q=lookup",
        headers={"Authorization": "Bearer viewer-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["events"][0]["status"] == "error"
    assert payload["events"][0]["trace_id"] == "trace_privat"
    assert payload["events"][0]["session_id"].startswith("session-")
    assert "detail" not in payload["events"][0]


def test_search_events_developer_payload_keeps_detail() -> None:
    app = _app()
    app.state.event_store.add(
        DashboardEvent(
            event_type="span_end",
            status=EventStatus.ERROR,
            detail={"stack": "visible"},
        )
    )
    client = TestClient(app)

    response = client.get(
        "/api/events/search?status=error",
        headers={"Authorization": "Bearer developer-token"},
    )

    assert response.status_code == 200
    assert response.json()["events"][0]["detail"] == {"stack": "visible"}


def test_websocket_replays_buffer() -> None:
    app = _app()
    app.state.event_buffer.add(DashboardEvent(event_type="trace_start", status=EventStatus.ACTIVE))
    client = TestClient(app)

    with client.websocket_connect("/ws/dashboard?token=viewer-token") as websocket:
        message = websocket.receive_json()

    assert message["type"] == "replay"
    assert message["events"][0]["event_type"] == "trace_start"


def test_dev_event_endpoint_is_disabled_by_default() -> None:
    client = TestClient(_app())

    response = client.post(
        "/api/dev/events",
        headers={"Authorization": "Bearer developer-token"},
        json={"event_type": "trace_start", "status": "active"},
    )

    assert response.status_code == 404


def test_dev_event_endpoint_requires_developer_role() -> None:
    client = TestClient(_app(enable_dev_tools=True))

    response = client.post(
        "/api/dev/events",
        headers={"Authorization": "Bearer viewer-token"},
        json={"event_type": "trace_start", "status": "active"},
    )

    assert response.status_code == 403


def test_dev_event_endpoint_broadcasts_to_websocket() -> None:
    app = _app(enable_dev_tools=True)
    client = TestClient(app)

    with client.websocket_connect("/ws/dashboard?token=viewer-token") as websocket:
        assert websocket.receive_json()["type"] == "replay"

        response = client.post(
            "/api/dev/events",
            headers={"Authorization": "Bearer developer-token"},
            json={
                "event_type": "span_start",
                "status": "active",
                "node_id": "node-orchestrator",
                "summary": "Orchestrator started",
                "detail": {"hidden": True},
            },
        )

        message = websocket.receive_json()

    assert response.status_code == 200
    assert message["type"] == "event"
    assert message["event"]["node_id"] == "node-orchestrator"
    assert "detail" not in message["event"]


def _app(enable_dev_tools: bool = False) -> FastAPI:
    event_store_path = Path(tempfile.mkdtemp()) / "events.db"
    settings = Settings(
        auth_token=SecretStr("viewer-token"),
        developer_auth_token=SecretStr("developer-token"),
        enable_redis_subscriber=False,
        enable_dev_tools=enable_dev_tools,
        event_store_path=event_store_path,
    )
    return create_app(settings)
