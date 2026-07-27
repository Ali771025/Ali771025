from __future__ import annotations

import unittest

from safe_autonomy.advisory import AdvisoryProposal, EvidenceGate
from safe_autonomy.hybrid_rag import RagResult
from safe_autonomy.sensor_contracts import TelemetryFrame


NOW = 1_000


def frame() -> TelemetryFrame:
    return TelemetryFrame(
        "tf-1", NOW, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0,
        80.0, 1.0, 0, (), ("gps-1", "imu-1", "battery-1"),
    )


class AdvisoryTests(unittest.TestCase):
    def test_parser_rejects_direct_numeric_command_field(self) -> None:
        payload = {
            "schema_version": "1.0", "proposal": "HOLD", "risk_class": "HIGH",
            "reason": "stale", "evidence_ids": ["telemetry:tf-1"], "confidence": 0.9,
            "requires_human_confirmation": False, "expires_at_ms": NOW + 1_000,
            "waypoint": [1, 2, 3],
        }
        with self.assertRaises(ValueError):
            AdvisoryProposal.from_dict(payload, "r1", "test-model", NOW)

    def test_evidence_gate_rejects_unknown_evidence_and_long_ttl(self) -> None:
        payload = {
            "schema_version": "1.0", "proposal": "RETURN", "risk_class": "HIGH",
            "reason": "battery", "evidence_ids": ["unknown"], "confidence": 0.9,
            "requires_human_confirmation": True, "expires_at_ms": NOW + 10_000,
        }
        proposal = AdvisoryProposal.from_dict(payload, "r1", "test-model", NOW)
        rag = RagResult("q1", "battery", (), "hash")
        gate = EvidenceGate(maximum_ttl_ms=5_000).validate(proposal, frame(), rag, NOW)
        self.assertFalse(gate.passed)
        self.assertEqual(len(gate.reasons), 2)


if __name__ == "__main__":
    unittest.main()

