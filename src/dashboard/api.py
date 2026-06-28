"""FastAPI application: health, track endpoints, and the telemetry WebSocket.

The app is created via a factory bound to a hub and shared session state. The
embedded single-page UI renders the live track map (car GPS dot + trail), live
timing, inputs, a real-time delta, and the AI engineer's lap analysis - all fed
by the ``session`` / ``telemetry`` / ``lap`` / ``advice`` envelopes.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable, Coroutine
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse

from src import __version__
from src.dashboard.hub import TelemetryHub
from src.dashboard.state import DashboardState

Producer = Callable[[], Coroutine[Any, Any, None]]

_INDEX_PATH = Path(__file__).parent / "static" / "index.html"


def _read_index() -> str:
    """Read the dashboard HTML from disk on each request.

    Reading per request (instead of caching at import time) means UI edits to
    ``static/index.html`` are picked up on the next page load without a server
    restart. The file is small and loaded infrequently, so the cost is trivial.
    """
    return _INDEX_PATH.read_text(encoding="utf-8")


def create_app(
    hub: TelemetryHub, state: DashboardState, *, producer: Producer | None = None
) -> FastAPI:
    """Build the dashboard FastAPI application bound to *hub* and *state*."""

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        task: asyncio.Task[None] | None = None
        if producer is not None:
            task = asyncio.create_task(producer())
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="AI-TrackEngineer", version=__version__, lifespan=lifespan)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/track")
    async def track() -> dict[str, Any]:
        if state.session is None:
            raise HTTPException(status_code=503, detail="no active session")
        return state.session

    @app.get("/api/track/map.png")
    async def track_map() -> FileResponse:
        if state.map_png is None or not state.map_png.is_file():
            raise HTTPException(status_code=404, detail="no track map available")
        return FileResponse(state.map_png, media_type="image/png")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return _read_index()

    @app.websocket("/ws/telemetry")
    async def telemetry_ws(websocket: WebSocket) -> None:
        queue = hub.subscribe()
        await websocket.accept()
        try:
            if state.session is not None:
                await websocket.send_json(state.session)
            while True:
                message = await queue.get()
                await websocket.send_json(message)
        except WebSocketDisconnect:
            pass
        finally:
            hub.unsubscribe(queue)

    return app
