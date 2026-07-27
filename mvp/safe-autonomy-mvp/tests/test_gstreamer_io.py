from __future__ import annotations

import json
import queue
import unittest
from pathlib import Path

from safe_autonomy.gstreamer_io import DropOldestQueue, validate_low_latency_pipeline


ROOT = Path(__file__).resolve().parents[1]


class GStreamerIoTests(unittest.TestCase):
    def test_drop_oldest_queue_never_accumulates_stale_frames(self) -> None:
        frames: DropOldestQueue[int] = DropOldestQueue(2)
        frames.put(1)
        frames.put(2)
        frames.put(3)
        self.assertEqual(frames.dropped_count, 1)
        self.assertEqual(frames.get(0), 2)
        self.assertEqual(frames.get(0), 3)
        with self.assertRaises(queue.Empty):
            frames.get(0.001)

    def test_all_camera_profiles_enforce_low_latency_appsink(self) -> None:
        configuration = json.loads((ROOT / "config/camera.gstreamer.dev.json").read_text(encoding="utf-8"))
        for name, profile in configuration["profiles"].items():
            with self.subTest(profile=name):
                self.assertEqual(validate_low_latency_pipeline(profile["pipeline"]), ())

    def test_unsafe_pipeline_is_rejected_by_validator(self) -> None:
        problems = validate_low_latency_pipeline("videotestsrc ! appsink name=camera_sink")
        self.assertGreaterEqual(len(problems), 3)


if __name__ == "__main__":
    unittest.main()
