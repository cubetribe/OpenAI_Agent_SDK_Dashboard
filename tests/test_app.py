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


def test_websocket_replays_buffer() -> None:
    app = _app()
    app.state.event_buffer.add(DashboardEvent(event_type="trace_start", status=EventStatus.ACTIVE))
    client = TestClient(app)

    with client.websocket_connect("/ws/dashboard?token=viewer-token") as websocket:
        message = websocket.receive_json()

    assert message["type"] == "replay"
    assert message["events"][0]["event_type"] == "trace_start"


def _app() -> FastAPI:
    settings = Settings(
        auth_token=SecretStr("viewer-token"),
        developer_auth_token=SecretStr("developer-token"),
        enable_redis_subscriber=False,
    )
    return create_app(settings)
