from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from safe_autonomy.map_ingestion import MapAnalyzer, MapUploadService
from safe_autonomy.mission_contracts import MapStatus


class MapIngestionTests(unittest.TestCase):
    def test_geojson_geofence_obstacle_and_risk_are_rasterized(self) -> None:
        payload = {
            "type": "FeatureCollection",
            "properties": {
                "coordinate_system": "LOCAL_ENU", "resolution_m": 1.0,
                "origin_x_m": 0.0, "origin_y_m": 0.0,
                "width_cells": 20, "height_cells": 20,
            },
            "features": [
                {"type": "Feature", "properties": {"layer": "geofence"}, "geometry": {"type": "Polygon", "coordinates": [[[1, 1], [18, 1], [18, 18], [1, 18], [1, 1]]]}},
                {"type": "Feature", "properties": {"layer": "obstacle"}, "geometry": {"type": "Polygon", "coordinates": [[[8, 8], [11, 8], [11, 11], [8, 11], [8, 8]]]}},
                {"type": "Feature", "properties": {"layer": "risk", "risk": 0.7}, "geometry": {"type": "Polygon", "coordinates": [[[3, 3], [6, 3], [6, 6], [3, 6], [3, 3]]]}},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "map.geojson"
            path.write_text(json.dumps(payload), encoding="utf-8")
            mission_map = MapUploadService().ingest(path)
        self.assertEqual(mission_map.occupancy_at((0, 0)), 1)
        self.assertEqual(mission_map.occupancy_at((9, 9)), 1)
        self.assertEqual(mission_map.occupancy_at((5, 5)), 0)
        self.assertAlmostEqual(mission_map.risk_at((5, 5)), 0.7)
        analysis = MapAnalyzer().analyze(mission_map)
        self.assertGreater(analysis.occupied_cells, 0)
        self.assertGreater(analysis.free_cells, 0)
        self.assertIn(analysis.status, {MapStatus.VALID, MapStatus.DEGRADED})

    def test_ros_pgm_and_yaml_are_loaded_with_bottom_left_origin(self) -> None:
        pgm = "P2\n3 2\n255\n0 255 205\n255 255 255\n"
        yaml = "resolution: 0.5\norigin: [10.0, 20.0, 0.0]\noccupied_thresh: 0.65\nfree_thresh: 0.196\nnegate: 0\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "grid.pgm"
            path.write_text(pgm, encoding="ascii")
            path.with_suffix(".yaml").write_text(yaml, encoding="utf-8")
            mission_map = MapUploadService().ingest(path)
        self.assertEqual((mission_map.width_cells, mission_map.height_cells), (3, 2))
        self.assertEqual((mission_map.origin_x_m, mission_map.origin_y_m), (10.0, 20.0))
        self.assertEqual(mission_map.occupancy_at((0, 1)), 1)
        self.assertEqual(mission_map.occupancy_at((1, 1)), 0)
        self.assertEqual(mission_map.occupancy_at((2, 1)), 2)

    def test_map_cell_limit_rejects_oversized_upload(self) -> None:
        payload = {
            "type": "FeatureCollection",
            "properties": {"resolution_m": 1, "width_cells": 100, "height_cells": 100},
            "features": [{"type": "Feature", "properties": {"layer": "obstacle"}, "geometry": {"type": "Point", "coordinates": [1, 1]}}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.geojson"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                MapUploadService(maximum_cells=100).ingest(path)

    def test_binary_pgm_preserves_whitespace_valued_first_pixel(self) -> None:
        raw = b"P5\n2 1\n255\n" + bytes([10, 255])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "binary.pgm"
            path.write_bytes(raw)
            mission_map = MapUploadService().ingest(path)
        self.assertEqual(mission_map.occupancy_at((0, 0)), 1)
        self.assertEqual(mission_map.occupancy_at((1, 0)), 0)


if __name__ == "__main__":
    unittest.main()
