# Configuration

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string. |
| `DASHBOARD_REDIS_CHANNEL` | `agent:traces` | Pub/Sub channel for trace events. |
| `DASHBOARD_AUTH_TOKEN` | development token | Viewer token. Must be changed outside local development. |
| `DASHBOARD_DEVELOPER_AUTH_TOKEN` | unset | Developer token for diagnostic payloads. |
| `DASHBOARD_REPLAY_BUFFER_SIZE` | `50` | Number of recent events replayed to new clients. |
| `DASHBOARD_CORS_ORIGINS` | `http://localhost:8090` | Comma-separated browser origins. |
| `DASHBOARD_CONFIG_PATH` | bundled default config | Path to workflow graph config. |
| `DASHBOARD_ENABLE_REDIS_SUBSCRIBER` | `true` | Disable for isolated tests or UI-only local runs. |

## Graph Config

Graph config is JSON and should be tenant-specific at deploy time. Source code must stay generic.

Required top-level keys:

- `brand`: product name and UI colors.
- `nodes`: agent and tool nodes.
- `edges`: visual links between nodes.
- `eventMappings`: mapping from event identifiers to graph nodes.

## Token Roles

- Viewer token: status-level visibility, no prompt or tool payload details.
- Developer token: diagnostic payload visibility for trusted maintainers.

Browser WebSockets use a token query parameter because browsers cannot set arbitrary authorization
headers for native WebSocket connections. Production reverse proxies should avoid logging query
strings or should terminate auth before forwarding to the dashboard.
