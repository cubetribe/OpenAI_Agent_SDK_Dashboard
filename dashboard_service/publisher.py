from __future__ import annotations

import os
from typing import Any, Protocol

from redis import Redis

from dashboard_service.events import DashboardEvent


class DashboardEventPublisher(Protocol):
    """Publishing boundary used by upstream workflow integrations."""

    def publish(self, event: DashboardEvent) -> None:
        """Publish one normalized dashboard event."""

    def close(self) -> None:
        """Release publisher resources."""


class RedisDashboardPublisher:
    """Publish dashboard events to the Redis Pub/Sub channel consumed by the service."""

    def __init__(self, redis_url: str, channel: str, client: Any | None = None) -> None:
        self.redis_url = redis_url
        self.channel = channel
        self._client: Any = client or Redis.from_url(redis_url, decode_responses=True)

    @classmethod
    def from_env(cls) -> RedisDashboardPublisher:
        return cls(
            redis_url=os.environ.get("REDIS_URL", "redis://redis:6379/0"),
            channel=os.environ.get("DASHBOARD_REDIS_CHANNEL", "agent:traces"),
        )

    def publish(self, event: DashboardEvent) -> None:
        self._client.publish(self.channel, event.model_dump_json())

    def close(self) -> None:
        self._client.close()
