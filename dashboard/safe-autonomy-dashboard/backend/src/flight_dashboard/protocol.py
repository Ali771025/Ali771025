from __future__ import annotations

import hmac
import hashlib
import json
import zlib
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from .models import Envelope


ALLOWED_TOPICS = {
    "telemetry",
    "flight_assessment",
    "vision",
    "route_candidates",
    "module_health",
    "alert",
    "scenario_report",
}


class ProtocolError(ValueError):
    pass


def canonical_crc32(data: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in data.items() if key not in {"crc32", "hmac_sha256"}}
    encoded = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return f"{zlib.crc32(encoded) & 0xFFFFFFFF:08x}"


def canonical_hmac(data: dict[str, Any], secret: str) -> str:
    unsigned = {key: value for key, value in data.items() if key not in {"crc32", "hmac_sha256"}}
    encoded = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(secret.encode("utf-8"), encoded, hashlib.sha256).hexdigest()


def parse_envelope(raw: bytes | str, shared_secret: str | None = None) -> Envelope:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProtocolError("invalid JSON") from exc
    if not isinstance(data, dict):
        raise ProtocolError("envelope must be an object")
    try:
        envelope = Envelope.model_validate(data)
    except ValidationError as exc:
        raise ProtocolError(str(exc)) from exc
    if envelope.topic not in ALLOWED_TOPICS:
        raise ProtocolError(f"unsupported topic: {envelope.topic}")
    if envelope.crc32 and canonical_crc32(data) != envelope.crc32.lower():
        raise ProtocolError("crc32 mismatch")
    if shared_secret:
        provided = str(data.get("hmac_sha256") or "").lower()
        expected = canonical_hmac(data, shared_secret)
        if not hmac.compare_digest(provided, expected):
            raise ProtocolError("hmac signature invalid")
    return envelope


@dataclass
class SequenceTracker:
    last: dict[tuple[str, str], int] = field(default_factory=dict)
    dropped: int = 0
    out_of_order: int = 0

    def observe(self, envelope: Envelope) -> None:
        key = (envelope.source, envelope.topic)
        previous = self.last.get(key)
        if previous is not None:
            if envelope.sequence_no <= previous:
                self.out_of_order += 1
            elif envelope.sequence_no > previous + 1:
                self.dropped += envelope.sequence_no - previous - 1
        if previous is None or envelope.sequence_no > previous:
            self.last[key] = envelope.sequence_no
