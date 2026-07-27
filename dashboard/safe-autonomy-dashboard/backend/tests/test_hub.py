import time
import uuid

import pytest

from flight_dashboard.hub import TelemetryHub
from flight_dashboard.models import Envelope


def event(sequence):
    return Envelope(
        message_id=str(uuid.uuid4()), topic="telemetry", source="test", sequence_no=sequence,
        sent_at_ms=int(time.time() * 1000), payload={"sequence": sequence},
    )


@pytest.mark.asyncio
async def test_subscriber_drops_oldest_and_tracks_sequence_gap():
    hub = TelemetryHub(queue_size=2)
    _, subscriber = await hub.subscribe()
    await hub.publish(event(1), "udp")
    await hub.publish(event(3), "udp")
    await hub.publish(event(4), "udp")
    assert subscriber.dropped == 1
    assert hub.sequences.dropped == 1
    assert (await subscriber.queue.get())["sequence_no"] == 3

