from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dashboard_service.events import ClientRole, DashboardEvent, EventStatus


@dataclass(frozen=True)
class EventSearchQuery:
    status: list[EventStatus] | None = None
    event_type: list[str] | None = None
    node_id: str | None = None
    trace_id: str | None = None
    session_id: str | None = None
    text: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    limit: int = 100
    offset: int = 0


class SQLiteEventStore:
    """SQLite archive for normalized dashboard events."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._connection = self._connect(path)
        self._migrate()

    def add(self, event: DashboardEvent) -> None:
        timestamp = event.timestamp.isoformat()
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO events (
                    event_id,
                    event_type,
                    status,
                    timestamp,
                    trace_id,
                    span_id,
                    parent_span_id,
                    session_id,
                    node_id,
                    agent_id,
                    tool_name,
                    span_type,
                    duration_ms,
                    summary,
                    message,
                    event_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.event_type,
                    event.status.value,
                    timestamp,
                    event.trace_id,
                    event.span_id,
                    event.parent_span_id,
                    event.session_id,
                    event.node_id,
                    event.agent_id,
                    event.tool_name,
                    event.span_type,
                    event.duration_ms,
                    event.summary,
                    event.message,
                    event.model_dump_json(),
                ),
            )

    def search(
        self,
        query: EventSearchQuery,
        role: ClientRole,
    ) -> tuple[list[dict[str, Any]], int]:
        where, parameters = self._where_clause(query)
        limit = min(max(query.limit, 1), 500)
        offset = max(query.offset, 0)

        with self._lock:
            count_row = self._connection.execute(
                f"SELECT COUNT(*) AS total FROM events {where}",
                parameters,
            ).fetchone()
            rows = self._connection.execute(
                f"""
                SELECT event_json
                FROM events
                {where}
                ORDER BY timestamp DESC, rowid DESC
                LIMIT ? OFFSET ?
                """,
                [*parameters, limit, offset],
            ).fetchall()

        events = [
            DashboardEvent.model_validate_json(str(row["event_json"])).to_client_payload(role)
            for row in rows
        ]
        return events, int(count_row["total"]) if count_row is not None else 0

    def latest(self, limit: int) -> list[DashboardEvent]:
        bounded_limit = min(max(limit, 1), 500)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT event_json
                FROM events
                ORDER BY timestamp DESC, rowid DESC
                LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()
        events = [DashboardEvent.model_validate_json(str(row["event_json"])) for row in rows]
        events.reverse()
        return events

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @staticmethod
    def _connect(path: Path) -> sqlite3.Connection:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _migrate(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    trace_id TEXT,
                    span_id TEXT,
                    parent_span_id TEXT,
                    session_id TEXT,
                    node_id TEXT,
                    agent_id TEXT,
                    tool_name TEXT,
                    span_type TEXT,
                    duration_ms INTEGER,
                    summary TEXT,
                    message TEXT,
                    event_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_events_timestamp
                    ON events (timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_events_status_timestamp
                    ON events (status, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_events_type_timestamp
                    ON events (event_type, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_events_node_timestamp
                    ON events (node_id, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_events_trace_timestamp
                    ON events (trace_id, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_events_session_timestamp
                    ON events (session_id, timestamp DESC);
                """
            )

    @staticmethod
    def _where_clause(query: EventSearchQuery) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []

        if query.status:
            placeholders = ", ".join("?" for _ in query.status)
            clauses.append(f"status IN ({placeholders})")
            parameters.extend(status.value for status in query.status)

        if query.event_type:
            placeholders = ", ".join("?" for _ in query.event_type)
            clauses.append(f"event_type IN ({placeholders})")
            parameters.extend(query.event_type)

        _add_exact_filter(clauses, parameters, "node_id", query.node_id)
        _add_exact_filter(clauses, parameters, "trace_id", query.trace_id)
        _add_exact_filter(clauses, parameters, "session_id", query.session_id)

        if query.since is not None:
            clauses.append("timestamp >= ?")
            parameters.append(query.since.isoformat())

        if query.until is not None:
            clauses.append("timestamp <= ?")
            parameters.append(query.until.isoformat())

        if query.text:
            clauses.append(
                """
                (
                    event_type LIKE ?
                    OR node_id LIKE ?
                    OR agent_id LIKE ?
                    OR tool_name LIKE ?
                    OR span_type LIKE ?
                    OR summary LIKE ?
                    OR message LIKE ?
                )
                """
            )
            like_value = f"%{query.text}%"
            parameters.extend([like_value] * 7)

        if not clauses:
            return "", parameters
        return f"WHERE {' AND '.join(clauses)}", parameters


def _add_exact_filter(
    clauses: list[str],
    parameters: list[Any],
    column: str,
    value: str | None,
) -> None:
    if value is None:
        return
    clauses.append(f"{column} = ?")
    parameters.append(value)
