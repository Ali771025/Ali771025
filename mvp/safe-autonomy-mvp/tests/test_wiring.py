from __future__ import annotations

import copy
import unittest
from pathlib import Path

from safe_autonomy.wiring import load_wiring, validate_wiring, wiring_checksum


ROOT = Path(__file__).resolve().parents[1]


class WiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.configuration = load_wiring(ROOT / "config/system.wiring.json")

    def test_declared_system_wiring_is_valid_and_reproducible(self) -> None:
        self.assertEqual(validate_wiring(self.configuration), ())
        self.assertEqual(wiring_checksum(self.configuration), wiring_checksum(copy.deepcopy(self.configuration)))

    def test_advisory_to_actuator_path_is_rejected(self) -> None:
        unsafe = copy.deepcopy(self.configuration)
        unsafe["modules"].append({
            "id": "actuator_output",
            "authority": "actuator",
            "inputs": {"proposal": "AdvisoryProposal.v1"},
            "outputs": {},
        })
        unsafe["connections"].append({
            "source": "transformer_advisory.proposal",
            "target": "actuator_output.proposal",
            "contract": "AdvisoryProposal.v1",
            "queue_policy": "latest_only",
            "max_age_ms": 100,
        })
        problems = validate_wiring(unsafe)
        self.assertTrue(any("forbidden advisory-to-control path" in item for item in problems))
        self.assertTrue(any("outside this developer build" in item for item in problems))

    def test_contract_mismatch_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.configuration)
        invalid["connections"][0]["contract"] = "Wrong.v1"
        self.assertTrue(any("contract mismatch" in item for item in validate_wiring(invalid)))

    def test_px4_command_contract_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.configuration)
        invalid["modules"][0]["outputs"]["unsafe"] = "VehicleCommand"
        self.assertTrue(any("forbidden contract" in item for item in validate_wiring(invalid)))


if __name__ == "__main__":
    unittest.main()
