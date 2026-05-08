from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as redis

from dashboard_service.events import DashboardEvent, event_from_mapping

EventCallback = Callable[[DashboardEvent], Awaitable[None]]

LOGGER = logging.getLogger(__name__)


class RedisSubscriber:
    """Subscribe to Redis Pub/Sub and forward normalized dashboard events."""

    def __init__(self, redis_url: str, channel: str, callback: EventCallback) -> None:
        self.redis_url = redis_url
        self.channel = channel
        self.callback = callback
        self._stopped = asyncio.Event()

    async def run(self) -> None:
        client: Any = redis.from_url(self.redis_url, decode_responses=True)
        pubsub: Any = client.pubsub()

        try:
            await pubsub.subscribe(self.channel)
            async for message in pubsub.listen():
                if self._stopped.is_set():
                    break
                if message.get("type") != "message":
                    continue

                event = self._decode_message(message.get("data"))
                if event is None:
                    continue
                await self.callback(event)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("Redis subscriber stopped unexpectedly")
            raise
        finally:
            await pubsub.unsubscribe(self.channel)
            await pubsub.aclose()
            await client.aclose()

    async def stop(self) -> None:
        self._stopped.set()

    @staticmethod
    def _decode_message(raw_data: object) -> DashboardEvent | None:
        if raw_data is None:
            return None

        try:
            if isinstance(raw_data, bytes):
                raw_data = raw_data.decode("utf-8")
            payload: Any = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        except json.JSONDecodeError:
            LOGGER.warning("Ignored non-JSON Redis message")
            return None

        if not isinstance(payload, dict):
            LOGGER.warning("Ignored Redis message with non-object payload")
            return None

        return event_from_mapping(payload)
