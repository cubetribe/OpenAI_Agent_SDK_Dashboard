# Event Archive

## Purpose

The dashboard archives every normalized workflow event in SQLite so operators and developers can
search historical activity without opening container logs or upstream application log files.

SQLite is intentionally the first storage backend:

- no separate database container is required
- the archive ships inside the dashboard container runtime
- data persists through a Docker volume
- indexed search is enough for the current event volume and operational questions

If a deployment later needs multi-node writes, long retention windows, or heavy analytics, the event
store boundary can be extended to PostgreSQL without changing the browser or publisher contracts.

## Storage Location

The default local path is `data/dashboard.db`. Docker sets:

```text
DASHBOARD_EVENT_STORE_PATH=/data/dashboard.db
```

The Compose stack mounts `/data` as the `dashboard_data` named volume.

## Query API

Search events:

```http
GET /api/events/search
Authorization: Bearer <viewer-or-developer-token>
```

Supported filters:

- `status`: repeatable, one of `active`, `success`, `error`, `idle`, `unknown`
- `event_type`: repeatable event type
- `node_id`: graph node ID
- `trace_id`: exact trace ID
- `session_id`: exact raw session ID for developer workflows
- `q`: text search across event type, node, agent, tool, span type, summary, and message
- `since`: ISO timestamp lower bound
- `until`: ISO timestamp upper bound
- `limit`: 1 to 500, default 100
- `offset`: pagination offset, default 0

The browser event panel exposes the same search API with status and text filters. Live events still
arrive through WebSocket; archived searches replace the visible feed with the latest matching rows.

Examples:

```bash
curl -H "Authorization: Bearer $DASHBOARD_DEVELOPER_AUTH_TOKEN" \
  "http://localhost:8090/api/events/search?status=error&limit=50"
```

```bash
curl -H "Authorization: Bearer $DASHBOARD_DEVELOPER_AUTH_TOKEN" \
  "http://localhost:8090/api/events/search?q=lookup&node_id=node-tool"
```

## Redaction

Viewer-token responses use the same redaction policy as live WebSocket events:

- trace and span IDs are shortened
- session IDs are pseudonymized
- metadata is emptied
- developer `detail` payloads are removed

Developer-token responses can include full normalized event details. Keep developer tokens restricted
to trusted maintainers.

## Operations

The event store uses SQLite WAL mode for reliable local writes. Back up the Docker volume if the
archive is operationally important:

```bash
docker run --rm -v agent_sdk_dashboard_dashboard_data:/data -v "$PWD":/backup alpine \
  cp /data/dashboard.db /backup/dashboard.db
```

For retention, start with operational policy rather than automatic deletion. The dashboard currently
keeps all archived events in the SQLite file until an operator rotates or backs up the database.
