#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish neutral demo events to a local dashboard."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8090", help="Dashboard base URL.")
    parser.add_argument("--token", required=True, help="Developer token.")
    parser.add_argument("--delay", type=float, default=0.75, help="Delay between demo events.")
    parser.add_argument(
        "--scenario",
        choices=["success", "error"],
        default="success",
        help="Demo scenario to publish.",
    )
    args = parser.parse_args()

    endpoint = f"{args.base_url.rstrip('/')}/api/dev/events"
    for event in _events(args.scenario):
        event["timestamp"] = datetime.now(UTC).isoformat()
        _post_event(endpoint, args.token, event)
        print(f"{event['status']:>7} {event['summary']}")
        time.sleep(args.delay)

    return 0


def _post_event(endpoint: str, token: str, event: dict[str, Any]) -> None:
    body = json.dumps(event).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=5) as response:
            if response.status != 200:
                msg = f"Unexpected response status: {response.status}"
                raise RuntimeError(msg)
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        msg = f"Dashboard rejected demo event with HTTP {exc.code}: {details}"
        raise RuntimeError(msg) from exc


def _events(scenario: str) -> list[dict[str, Any]]:
    events = [
        _event("trace_start", "active", "node-ingress", "Incoming request received"),
        _event("span_start", "active", "node-orchestrator", "Orchestrator started"),
        _event("span_end", "success", "node-orchestrator", "Orchestrator selected route", 210),
        _event("span_start", "active", "node-tool", "Tool lookup started"),
    ]

    if scenario == "error":
        events.extend(
            [
                _event("span_end", "error", "node-tool", "Tool lookup failed", 840),
                _event("trace_end", "error", "node-response", "Workflow ended with error", 1050),
            ]
        )
        return events

    events.extend(
        [
            _event("span_end", "success", "node-tool", "Tool lookup finished", 430),
            _event("span_start", "active", "node-knowledge", "Knowledge lookup started"),
            _event("span_end", "success", "node-knowledge", "Knowledge lookup finished", 350),
            _event("span_start", "active", "node-response", "Response generation started"),
            _event("trace_end", "success", "node-response", "Workflow completed", 1320),
        ]
    )
    return events


def _event(
    event_type: str,
    status: str,
    node_id: str,
    summary: str,
    duration_ms: int | None = None,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "status": status,
        "node_id": node_id,
        "trace_id": "trace_demo_000000000000000000000001",
        "span_id": f"span_{node_id}",
        "session_id": "demo-session",
        "summary": summary,
        "duration_ms": duration_ms,
        "metadata": {},
        "detail": {},
    }


if __name__ == "__main__":
    sys.exit(main())
