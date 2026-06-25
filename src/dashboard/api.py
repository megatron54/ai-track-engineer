"""FastAPI application: health, a minimal live page, and the telemetry WebSocket.

The app is created via a factory so tests can inject their own hub. The embedded
HTML page is a lightweight placeholder for live viewing until the React frontend
lands; it connects to the same WebSocket the production UI will use.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from src import __version__
from src.dashboard.hub import TelemetryHub
from src.dashboard.serialization import frame_to_payload

Producer = Callable[[], Coroutine[Any, Any, None]]

_CELL = (
    '<div class="cell"><div class="label">{label}</div>'
    '<div class="value" id="{id}">-</div></div>'
)

_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AI-TrackEngineer - Live Telemetry</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background: #111; color: #eee; margin: 2rem; }}
    h1 {{ font-size: 1.2rem; color: #6cf; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(120px, 1fr)); gap: 1rem; }}
    .cell {{ background: #1c1c1c; border-radius: 8px; padding: 1rem; }}
    .label {{ font-size: 0.75rem; color: #888; text-transform: uppercase; }}
    .value {{ font-size: 1.6rem; font-variant-numeric: tabular-nums; }}
    #status {{ color: #fc6; }}
  </style>
</head>
<body>
  <h1>AI-TrackEngineer - Live Telemetry</h1>
  <p>Connection: <span id="status">connecting...</span></p>
  <div class="grid">
    {speed}
    {rpm}
    {gear}
    {current}
    {last}
    {best}
  </div>
  <script>
    const set = (id, v) => {{ document.getElementById(id).textContent = v; }};
    const ws = new WebSocket(`ws://${{location.host}}/ws/telemetry`);
    ws.onopen = () => set("status", "live");
    ws.onclose = () => set("status", "disconnected");
    ws.onmessage = (e) => {{
      const d = JSON.parse(e.data);
      set("speed", d.speed_kmh); set("rpm", d.rpm); set("gear", d.gear);
      set("current", d.current_time); set("last", d.last_time); set("best", d.best_time);
    }};
  </script>
</body>
</html>
""".format(
    speed=_CELL.format(label="Speed (km/h)", id="speed"),
    rpm=_CELL.format(label="RPM", id="rpm"),
    gear=_CELL.format(label="Gear", id="gear"),
    current=_CELL.format(label="Current Lap", id="current"),
    last=_CELL.format(label="Last Lap", id="last"),
    best=_CELL.format(label="Best Lap", id="best"),
)


def create_app(hub: TelemetryHub, *, producer: Producer | None = None) -> FastAPI:
    """Build the dashboard FastAPI application bound to *hub*.

    Args:
        hub: The telemetry fan-out hub WebSocket clients subscribe to.
        producer: Optional async producer run as a background task for the app's
            lifetime (typically the capture pump). Cancelled cleanly on shutdown.
    """

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

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return _INDEX_HTML

    @app.websocket("/ws/telemetry")
    async def telemetry_ws(websocket: WebSocket) -> None:
        # Subscribe before accepting so no frame published between accept and
        # subscribe is missed.
        queue = hub.subscribe()
        await websocket.accept()
        try:
            while True:
                frame = await queue.get()
                await websocket.send_json(frame_to_payload(frame))
        except WebSocketDisconnect:
            pass
        finally:
            hub.unsubscribe(queue)

    return app
