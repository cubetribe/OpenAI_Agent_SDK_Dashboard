import json

from dashboard_service.events import DashboardEvent, EventStatus
from dashboard_service.publisher import RedisDashboardPublisher


class FakeRedisClient:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []
        self.closed = False

    def publish(self, channel: str, payload: str) -> None:
        self.published.append((channel, payload))

    def close(self) -> None:
        self.closed = True


def test_redis_publisher_serializes_dashboard_event() -> None:
    client = FakeRedisClient()
    publisher = RedisDashboardPublisher(
        redis_url="redis://example.invalid:6379/0",
        channel="agent:traces",
        client=client,
    )

    publisher.publish(DashboardEvent(event_type="trace_start", status=EventStatus.ACTIVE))

    channel, payload = client.published[0]
    assert channel == "agent:traces"
    assert json.loads(payload)["event_type"] == "trace_start"


def test_redis_publisher_closes_client() -> None:
    client = FakeRedisClient()
    publisher = RedisDashboardPublisher(
        redis_url="redis://example.invalid:6379/0",
        channel="agent:traces",
        client=client,
    )

    publisher.close()

    assert client.closed is True
