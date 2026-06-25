"""Batched telemetry writing to InfluxDB.

The hot path converts :class:`~src.telemetry.models.TelemetryFrame` objects into
time-series points and writes them in batches. The actual network sink is hidden
behind a :class:`TelemetryWriteBackend` protocol so the batching and point
mapping can be unit-tested with an in-memory fake, and the real InfluxDB client
stays a thin, swappable adapter.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from src.telemetry.models import TelemetryFrame

if TYPE_CHECKING:
    from src.config.settings import InfluxSettings

TELEMETRY_MEASUREMENT = "telemetry"


@dataclass(frozen=True)
class TelemetryPoint:
    """A single time-series point destined for InfluxDB."""

    measurement: str
    tags: dict[str, str]
    fields: dict[str, float]
    timestamp_s: float


def frame_to_point(frame: TelemetryFrame, *, session_id: str) -> TelemetryPoint:
    """Map a telemetry frame to an InfluxDB point.

    Tags are low-cardinality identifiers (session, track, car); fields are the
    numeric channels we want to query and chart.
    """
    physics = frame.physics
    graphics = frame.graphics
    static_info = frame.static_info
    return TelemetryPoint(
        measurement=TELEMETRY_MEASUREMENT,
        tags={
            "session": session_id,
            "track": static_info.track,
            "car": static_info.car_model,
        },
        fields={
            "speed_kmh": physics.speed_kmh,
            "rpm": float(physics.rpm),
            "gear": float(physics.gear),
            "gas": physics.gas,
            "brake": physics.brake,
            "fuel": physics.fuel,
            "normalized_position": graphics.normalized_car_position,
            "tyre_temp_fl": physics.tyre_core_temp.front_left,
            "tyre_temp_fr": physics.tyre_core_temp.front_right,
            "tyre_temp_rl": physics.tyre_core_temp.rear_left,
            "tyre_temp_rr": physics.tyre_core_temp.rear_right,
        },
        timestamp_s=frame.timestamp,
    )


class TelemetryWriteBackend(Protocol):
    """A sink that persists a batch of telemetry points."""

    async def write(self, points: Sequence[TelemetryPoint]) -> None: ...

    async def aclose(self) -> None: ...


class BatchingTelemetryWriter:
    """Buffer telemetry points and flush them to a backend in batches.

    Batching keeps the 60 Hz capture loop off the network: points accumulate in
    memory and are flushed when the batch fills or on an explicit flush (e.g. at
    the end of a lap or session).
    """

    def __init__(
        self,
        backend: TelemetryWriteBackend,
        *,
        session_id: str,
        batch_size: int = 200,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self._backend = backend
        self._session_id = session_id
        self._batch_size = batch_size
        self._buffer: list[TelemetryPoint] = []

    @property
    def buffered(self) -> int:
        """Number of points currently buffered (not yet flushed)."""
        return len(self._buffer)

    async def add(self, frame: TelemetryFrame) -> None:
        """Buffer a frame, flushing automatically when the batch fills."""
        self._buffer.append(frame_to_point(frame, session_id=self._session_id))
        if len(self._buffer) >= self._batch_size:
            await self.flush()

    async def flush(self) -> None:
        """Write any buffered points to the backend and clear the buffer."""
        if not self._buffer:
            return
        batch = self._buffer
        self._buffer = []
        await self._backend.write(batch)

    async def aclose(self) -> None:
        """Flush remaining points and close the backend."""
        await self.flush()
        await self._backend.aclose()

    async def __aenter__(self) -> BatchingTelemetryWriter:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()


class InfluxBackend:  # pragma: no cover - thin network adapter, exercised in integration only
    """A :class:`TelemetryWriteBackend` backed by InfluxDB.

    Kept intentionally thin; the batching and mapping logic (the parts worth
    testing) live in :class:`BatchingTelemetryWriter` and :func:`frame_to_point`.
    """

    def __init__(self, *, url: str, token: str, org: str, bucket: str) -> None:
        from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

        self._bucket = bucket
        self._client = InfluxDBClientAsync(url=url, token=token, org=org)

    @classmethod
    def from_settings(cls, settings: InfluxSettings) -> InfluxBackend:
        return cls(
            url=settings.url,
            token=settings.token,
            org=settings.org,
            bucket=settings.bucket,
        )

    async def write(self, points: Sequence[TelemetryPoint]) -> None:
        from influxdb_client import Point

        records = []
        for point in points:
            record = Point(point.measurement).time(int(point.timestamp_s * 1e9))
            for tag_key, tag_value in point.tags.items():
                record = record.tag(tag_key, tag_value)
            for field_key, field_value in point.fields.items():
                record = record.field(field_key, field_value)
            records.append(record)
        await self._client.write_api().write(bucket=self._bucket, record=records)

    async def aclose(self) -> None:
        await self._client.close()
