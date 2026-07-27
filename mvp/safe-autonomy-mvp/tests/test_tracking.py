from __future__ import annotations

import unittest

from safe_autonomy.tracking import DetectionCandidate, IoUTracker, intersection_over_union


class TrackingTests(unittest.TestCase):
    def test_iou_and_stable_track_identity(self) -> None:
        tracker = IoUTracker(minimum_iou=0.2, max_age_frames=2)
        first = tracker.update((DetectionCandidate(0, "target", 0.9, (10, 10, 30, 30)),), 0)
        second = tracker.update((DetectionCandidate(0, "target", 0.8, (12, 11, 32, 31)),), 1)
        self.assertEqual(first[0].track_id, second[0].track_id)
        self.assertGreater(intersection_over_union((10, 10, 30, 30), (12, 11, 32, 31)), 0.5)

    def test_track_expires_after_declared_age(self) -> None:
        tracker = IoUTracker(minimum_iou=0.2, max_age_frames=1)
        first = tracker.update((DetectionCandidate(0, "target", 0.9, (10, 10, 30, 30)),), 0)
        tracker.update((), 1)
        second = tracker.update((DetectionCandidate(0, "target", 0.9, (10, 10, 30, 30)),), 2)
        self.assertNotEqual(first[0].track_id, second[0].track_id)

    def test_different_classes_do_not_share_track(self) -> None:
        tracker = IoUTracker(minimum_iou=0.2)
        first = tracker.update((DetectionCandidate(0, "a", 0.9, (10, 10, 30, 30)),), 0)
        second = tracker.update((DetectionCandidate(1, "b", 0.9, (10, 10, 30, 30)),), 1)
        self.assertNotEqual(first[0].track_id, second[0].track_id)


if __name__ == "__main__":
    unittest.main()
