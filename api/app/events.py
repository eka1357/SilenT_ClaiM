"""In-process SSE event bus with monotonic event IDs and integration health tracking."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import deque
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from app.config import Settings, is_offline
from app.integrations.paytm import PENDING_SIMULATED_LABEL
from app.integrations.replay import HealthCallback, IntegrationMode
from app.models import now_ist

ALLOWED_SSE_EVENTS: frozenset[str] = frozenset(
    {
        "clock.tick",
        "shop.status",
        "detector.decision",
        "agent.step",
        "ask.sent",
        "ask.answered",
        "claim.filed",
        "batch.ready",
        "batch.approved",
        "refund.status",
        "integration.health",
    }
)


@dataclass(frozen=True, slots=True)
class SSEEvent:
    """Single server-sent event with sequential integer ID for reconnect resume."""

    id: int
    event: str
    data: dict[str, Any]
    ts: str = field(default_factory=lambda: now_ist().isoformat())

    def encode(self) -> str:
        """Format in canonical wire SSE text framing."""
        payload = json.dumps(self.data, ensure_ascii=False)
        return f"id: {self.id}\nevent: {self.event}\ndata: {payload}\n\n"


@dataclass
class _Subscriber:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[SSEEvent | None]


class EventBus:
    """Thread-safe in-process pub/sub bus driving GET /api/stream."""

    def __init__(self, *, max_history: int = 2000) -> None:
        self._lock = threading.Lock()
        self._next_id: int = 0
        self._history: deque[SSEEvent] = deque(maxlen=max_history)
        self._subscribers: list[_Subscriber] = []

    def publish(self, event: str, data: dict[str, Any]) -> SSEEvent:
        """Publish an event to the history ring buffer and all live subscribers."""
        if event not in ALLOWED_SSE_EVENTS:
            msg = f"Unsupported SSE event name: {event}"
            raise ValueError(msg)

        payload = dict(data)
        with self._lock:
            self._next_id += 1
            evt = SSEEvent(id=self._next_id, event=event, data=payload)
            self._history.append(evt)
            subscribers = list(self._subscribers)

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        for sub in subscribers:
            if running_loop is sub.loop:
                sub.queue.put_nowait(evt)
            elif not sub.loop.is_closed():
                sub.loop.call_soon_threadsafe(sub.queue.put_nowait, evt)
        return evt

    @property
    def events(self) -> list[SSEEvent]:
        """Return a snapshot of buffered events (useful for tests and diagnostics)."""
        with self._lock:
            return list(self._history)

    def history_after(self, last_event_id: int | None) -> list[SSEEvent]:
        """Return buffered events with id > last_event_id."""
        if last_event_id is None:
            return []
        with self._lock:
            return [evt for evt in self._history if evt.id > last_event_id]

    def close_all(self) -> None:
        """Signal all active subscribers to terminate their SSE streams cleanly."""
        with self._lock:
            subscribers = list(self._subscribers)
            self._subscribers.clear()

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        for sub in subscribers:
            if running_loop is sub.loop:
                sub.queue.put_nowait(None)
            elif not sub.loop.is_closed():
                sub.loop.call_soon_threadsafe(sub.queue.put_nowait, None)

    async def subscribe(
        self,
        *,
        last_event_id: int | None = None,
        heartbeat_seconds: float = 15.0,
    ) -> AsyncIterator[str]:
        """Yield SSE-formatted event frames, resuming after `last_event_id`."""
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[SSEEvent | None] = asyncio.Queue()
        sub = _Subscriber(loop=loop, queue=queue)

        with self._lock:
            missed = (
                [evt for evt in self._history if evt.id > last_event_id]
                if last_event_id is not None
                else []
            )
            self._subscribers.append(sub)

        try:
            seen_id = last_event_id or 0
            for evt in missed:
                seen_id = max(seen_id, evt.id)
                yield evt.encode()

            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                if item is None:
                    break
                if item.id <= seen_id:
                    continue
                seen_id = item.id
                yield item.encode()
        finally:
            with self._lock:
                if sub in self._subscribers:
                    self._subscribers.remove(sub)


@dataclass
class IntegrationHealthTracker:
    """Tracks current live/replay/down/simulated mode per integration and emits health changes."""

    bus: EventBus
    settings_getter: Callable[[], Settings]
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _modes: dict[str, str] = field(default_factory=dict)

    def _default_modes(self, cfg: Settings) -> dict[str, str]:
        offline = is_offline(cfg)
        base_mode = "replay" if offline else "live"
        paytm_mode = (
            "simulated"
            if cfg.paytm_mode.strip().lower() == "pending"
            else ("replay" if offline else "live")
        )
        return {
            "weather": base_mode,
            "sarvam": base_mode,
            "llm": base_mode,
            "paytm": paytm_mode,
        }

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Return health status dict suitable for GET /api/health."""
        cfg = self.settings_getter()
        defaults = self._default_modes(cfg)
        offline = is_offline(cfg)
        with self._lock:
            merged = {name: self._modes.get(name, default) for name, default in defaults.items()}

        # Enforce staging/offline invariants even after startup overrides.
        if offline:
            merged["weather"] = "replay" if merged["weather"] != "down" else "down"
            merged["sarvam"] = "replay" if merged["sarvam"] != "down" else "down"
            merged["llm"] = "replay" if merged["llm"] != "down" else "down"
        if cfg.paytm_mode.strip().lower() == "pending":
            merged["paytm"] = "simulated"

        out: dict[str, dict[str, Any]] = {}
        for name, mode in merged.items():
            label = (
                PENDING_SIMULATED_LABEL
                if name == "paytm" and mode == "simulated"
                else ("Replay" if mode == "replay" else ("Live" if mode == "live" else "Down"))
            )
            out[name] = {
                "mode": mode,
                "live": mode == "live",
                "replay": mode == "replay",
                "label": label,
            }
        return out

    def record(self, name: str, mode: IntegrationMode | str) -> None:
        """Record an integration mode observation and emit integration.health on changes."""
        cfg = self.settings_getter()
        normalized = str(mode)
        if name == "paytm" and cfg.paytm_mode.strip().lower() == "pending":
            normalized = "simulated"

        with self._lock:
            prev = self._modes.get(name)
            self._modes[name] = normalized

        if prev != normalized:
            sse_mode = "replay" if normalized == "simulated" else normalized
            if sse_mode in {"live", "replay", "down"}:
                self.bus.publish(
                    "integration.health",
                    {
                        "name": name,
                        "mode": sse_mode,
                        "live": sse_mode == "live",
                        "replay": sse_mode == "replay",
                    },
                )

    def make_callback(self, *, ignore_down_when_offline: bool = False) -> HealthCallback:
        """Build a HealthCallback compatible with app.integrations.* clients."""

        def _cb(name: str, mode: IntegrationMode) -> None:
            if ignore_down_when_offline and mode == "down" and is_offline(self.settings_getter()):
                return
            self.record(name, mode)

        return _cb


class SlidingWindowRateLimiter:
    """In-memory per-IP 60-second sliding-window rate limiter (docs/SECURITY.md)."""

    def __init__(
        self,
        *,
        limit_per_minute: int = 30,
        window_seconds: float = 60.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.limit_per_minute = limit_per_minute
        self.window_seconds = window_seconds
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def allow(self, client_key: str) -> bool:
        """Record one request from `client_key`; return False if limit is exceeded."""
        now = self._clock()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._hits.setdefault(client_key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit_per_minute:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        """Clear all rate-limit counters."""
        with self._lock:
            self._hits.clear()
