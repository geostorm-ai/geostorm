"""In-memory event bus for real-time run progress streaming."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class RunPhase(StrEnum):
    preparing = "preparing"
    querying = "querying"
    analyzing = "analyzing"
    complete = "complete"
    failed = "failed"


@dataclass
class RunProgressEvent:
    run_id: str
    phase: RunPhase
    completed: int
    failed: int
    total: int
    current_term: str | None = None
    current_provider: str | None = None
    status: str = "running"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["phase"] = self.phase.value
        return data


class ProgressBus:
    """Simple pub/sub using asyncio.Queue per subscriber."""

    def __init__(self) -> None:
        # run_id -> list of subscriber queues
        self._subscribers: dict[str, list[asyncio.Queue[RunProgressEvent]]] = {}

    def subscribe(self, run_id: str) -> asyncio.Queue[RunProgressEvent]:
        queue: asyncio.Queue[RunProgressEvent] = asyncio.Queue(maxsize=64)
        self._subscribers.setdefault(run_id, []).append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue[RunProgressEvent]) -> None:
        queues = self._subscribers.get(run_id, [])
        with contextlib.suppress(ValueError):
            queues.remove(queue)
        if not queues:
            self._subscribers.pop(run_id, None)

    def publish(self, event: RunProgressEvent) -> None:
        queues = self._subscribers.get(event.run_id, [])
        for queue in queues:
            if queue.full():
                # Drop oldest event (backpressure — slow client never blocks scheduler)
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.debug("Progress queue full for run %s, dropping event", event.run_id)


# Module-level singleton
progress_bus = ProgressBus()
