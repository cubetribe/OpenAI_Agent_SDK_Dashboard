# Local Live Testing

Use this workflow to verify the dashboard's browser, WebSocket, replay buffer, and event rendering
without connecting a real upstream agent application.

## Start the Dashboard

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"

DASHBOARD_ENABLE_REDIS_SUBSCRIBER=false \
DASHBOARD_ENABLE_DEV_TOOLS=true \
DASHBOARD_AUTH_TOKEN=viewer-token \
DASHBOARD_DEVELOPER_AUTH_TOKEN=developer-token \
uvicorn dashboard_service.main:create_app --factory --reload --port 8090
```

Open `http://localhost:8090` and connect with `viewer-token`.

## Publish Demo Events

In a second terminal:

```bash
. .venv/bin/activate
python scripts/publish_demo_events.py --token developer-token
```

For an error-state walkthrough:

```bash
python scripts/publish_demo_events.py --token developer-token --scenario error
```

Expected result:

- Connection state shows `Online`.
- Nodes on the workflow graph change state as events arrive.
- Runtime graph mode shows trace/span-derived cards and branch edges when configured with
  `dashboard_service/config/runtime.dashboard.json`.
- The workflow canvas zoom controls update the visible graph scale.
- The event feed fills with neutral demo events.
- Replay endpoint returns the recent events for new connections.

## Production Boundary

`DASHBOARD_ENABLE_DEV_TOOLS` must remain `false` outside local smoke tests. The dev endpoint does not
mutate upstream agent workflows, but it does inject synthetic events into the dashboard's in-memory
state and broadcast path.
