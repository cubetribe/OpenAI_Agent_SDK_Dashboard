from pathlib import Path

from dashboard_service.events import ClientRole, DashboardEvent, EventStatus
from dashboard_service.store import EventSearchQuery, SQLiteEventStore


def test_sqlite_store_searches_indexed_fields(tmp_path: Path) -> None:
    store = SQLiteEventStore(tmp_path / "events.db")
    store.add(
        DashboardEvent(
            event_type="span_end",
            status=EventStatus.ERROR,
            node_id="node-tool",
            summary="Tool lookup failed",
            detail={"stack": "hidden"},
        )
    )
    store.add(
        DashboardEvent(
            event_type="trace_end",
            status=EventStatus.SUCCESS,
            node_id="node-response",
            summary="Workflow completed",
        )
    )

    events, total = store.search(
        EventSearchQuery(status=[EventStatus.ERROR], text="lookup"),
        ClientRole.VIEWER,
    )

    assert total == 1
    assert events[0]["node_id"] == "node-tool"
    assert "detail" not in events[0]


def test_sqlite_store_latest_returns_oldest_to_newest(tmp_path: Path) -> None:
    store = SQLiteEventStore(tmp_path / "events.db")
    store.add(DashboardEvent(event_type="one", status=EventStatus.ACTIVE))
    store.add(DashboardEvent(event_type="two", status=EventStatus.SUCCESS))
    store.add(DashboardEvent(event_type="three", status=EventStatus.SUCCESS))

    events = store.latest(2)

    assert [event.event_type for event in events] == ["two", "three"]
