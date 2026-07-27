from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Any

from .models import Envelope
from .protocol import SequenceTracker


@dataclass
class Subscriber:
    queue: asyncio.Queue
    dropped: int = 0


class TelemetryHub:
    def __init__(self, queue_size: int = 128, history_size: int = 1200):
        self.queue_size = queue_size
        self.latest: dict[str, dict[str, Any]] = {}
        self.history: deque[dict[str, Any]] = deque(maxlen=history_size)
        self.subscribers: dict[str, Subscriber] = {}
        self.sequences = SequenceTracker()
        self.received = 0
        self.invalid = 0
        self.started_at_ms = int(time.time() * 1000)
        self._lock = asyncio.Lock()

    async def publish(self, envelope: Envelope, transport: str) -> dict[str, Any]:
        received_at_ms = int(time.time() * 1000)
        event = {
            "type": "topic_update",
            "topic": envelope.topic,
            "source": envelope.source,
            "sequence_no": envelope.sequence_no,
            "sent_at_ms": envelope.sent_at_ms,
            "received_at_ms": received_at_ms,
            "latency_ms": max(0, received_at_ms - envelope.sent_at_ms),
            "transport": transport,
            "payload": envelope.payload,
        }
        async with self._lock:
            self.sequences.observe(envelope)
            self.received += 1
            self.latest[envelope.topic] = event
            if envelope.topic == "telemetry":
                self.history.append(event)
            for subscriber in self.subscribers.values():
                if subscriber.queue.full():
                    try:
                        subscriber.queue.get_nowait()
                        subscriber.dropped += 1
                    except asyncio.QueueEmpty:
                        pass
                subscriber.queue.put_nowait(event)
        return event

    async def subscribe(self) -> tuple[str, Subscriber]:
        subscription_id = str(uuid.uuid4())
        subscriber = Subscriber(asyncio.Queue(maxsize=self.queue_size))
        async with self._lock:
            self.subscribers[subscription_id] = subscriber
        return subscription_id, subscriber

    async def unsubscribe(self, subscription_id: str) -> None:
        async with self._lock:
            self.subscribers.pop(subscription_id, None)

    def snapshot(self) -> dict[str, Any]:
        return {
            "topics": self.latest,
            "transport": {
                "received": self.received,
                "invalid": self.invalid,
                "sequence_gaps": self.sequences.dropped,
                "out_of_order": self.sequences.out_of_order,
                "subscribers": len(self.subscribers),
                "uptime_ms": int(time.time() * 1000) - self.started_at_ms,
            },
        }

    def telemetry_history(self, limit: int = 300) -> list[dict[str, Any]]:
        return list(self.history)[-limit:]
