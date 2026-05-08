import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette import status

from dashboard_service.broker import RedisSubscriber
from dashboard_service.events import ClientRole, DashboardEvent, EventBuffer, resolve_role
from dashboard_service.settings import Settings, get_settings

STATIC_DIR = Path(__file__).parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"


class ConnectionManager:
    def __init__(self, event_buffer: EventBuffer) -> None:
        self._event_buffer = event_buffer
        self._connections: dict[WebSocket, ClientRole] = {}

    async def connect(self, websocket: WebSocket, role: ClientRole) -> None:
        await websocket.accept()
        self._connections[websocket] = role
        await websocket.send_json({"type": "replay", "events": self._event_buffer.snapshot(role)})

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.pop(websocket, None)

    async def broadcast(self, event: DashboardEvent) -> None:
        for websocket, role in list(self._connections.items()):
            try:
                await websocket.send_json({"type": "event", "event": event.to_client_payload(role)})
            except RuntimeError:
                self.disconnect(websocket)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    event_buffer = EventBuffer(maxlen=app_settings.replay_buffer_size)
    manager = ConnectionManager(event_buffer)
    subscriber: RedisSubscriber | None = None
    subscriber_task: asyncio.Task[None] | None = None

    async def handle_event(event: DashboardEvent) -> None:
        event_buffer.add(event)
        await manager.broadcast(event)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        nonlocal subscriber, subscriber_task

        if app_settings.enable_redis_subscriber:
            subscriber = RedisSubscriber(
                redis_url=app_settings.redis_url,
                channel=app_settings.redis_channel,
                callback=handle_event,
            )
            subscriber_task = asyncio.create_task(subscriber.run())

        try:
            yield
        finally:
            if subscriber is not None:
                await subscriber.stop()
            if subscriber_task is not None:
                subscriber_task.cancel()
                with suppress(asyncio.CancelledError):
                    await subscriber_task

    app = FastAPI(
        title=app_settings.service_name,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )
    app.state.settings = app_settings
    app.state.event_buffer = event_buffer
    app.state.manager = manager

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Authorization"],
    )

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    async def http_role(
        authorization: Annotated[str | None, Header()] = None,
        token: Annotated[str | None, Query()] = None,
    ) -> ClientRole:
        resolved_token = token or _extract_bearer_token(authorization)
        role = resolve_role(resolved_token, app_settings.viewer_token, app_settings.developer_token)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing dashboard token.",
            )
        return role

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(INDEX_FILE)

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": app_settings.service_name,
            "redis_subscriber_enabled": app_settings.enable_redis_subscriber,
            "buffer_size": len(event_buffer),
        }

    @app.get("/api/config")
    async def dashboard_config() -> dict[str, Any]:
        return _load_dashboard_config(app_settings.config_path)

    @app.get("/api/events/replay")
    async def replay_events(role: Annotated[ClientRole, Depends(http_role)]) -> dict[str, Any]:
        return {"role": role.value, "events": event_buffer.snapshot(role)}

    @app.websocket("/ws/dashboard")
    async def dashboard_socket(websocket: WebSocket) -> None:
        role = _resolve_websocket_role(websocket, app_settings)
        if role is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await manager.connect(websocket, role)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return app


def _load_dashboard_config(config_path: Path) -> dict[str, Any]:
    resolved_path = config_path if config_path.is_absolute() else Path.cwd() / config_path
    with resolved_path.open(encoding="utf-8") as config_file:
        payload = json.load(config_file)
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dashboard config must be a JSON object.",
        )
    return payload


def _extract_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value:
        return None
    return value.strip()


def _resolve_websocket_role(websocket: WebSocket, settings: Settings) -> ClientRole | None:
    token = websocket.query_params.get("token") or _extract_bearer_token(
        websocket.headers.get("authorization")
    )
    return resolve_role(token, settings.viewer_token, settings.developer_token)
