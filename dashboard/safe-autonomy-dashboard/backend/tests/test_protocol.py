import json
import time
import uuid

import pytest

from flight_dashboard.protocol import ProtocolError, canonical_crc32, parse_envelope


def packet(sequence=1):
    value = {
        "schema_version": "1.0",
        "message_id": str(uuid.uuid4()),
        "topic": "telemetry",
        "source": "test-source",
        "sequence_no": sequence,
        "sent_at_ms": int(time.time() * 1000),
        "payload": {"battery_percent": 80},
    }
    value["crc32"] = canonical_crc32(value)
    return value


def test_valid_crc_packet():
    value = packet()
    assert parse_envelope(json.dumps(value)).sequence_no == 1


def test_rejects_tampered_packet():
    value = packet()
    value["payload"]["battery_percent"] = 1
    with pytest.raises(ProtocolError, match="crc32"):
        parse_envelope(json.dumps(value))


def test_rejects_unknown_topic():
    value = packet()
    value["topic"] = "raw_actuator"
    value["crc32"] = canonical_crc32(value)
    with pytest.raises(ProtocolError, match="unsupported"):
        parse_envelope(json.dumps(value))

