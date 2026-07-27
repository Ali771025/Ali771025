from __future__ import annotations

import hashlib
import json
import math
import re
from collections import deque
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from .mission_contracts import CoordinateSystem, MapAnalysis, MapFormat, MapStatus, MissionMap


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _point_in_ring(x: float, y: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        intersects = (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
        if intersects:
            inside = not inside
        j = i
    return inside


def _point_in_polygon(x: float, y: float, polygon: list[list[tuple[float, float]]]) -> bool:
    if not polygon or not _point_in_ring(x, y, polygon[0]):
        return False
    return not any(_point_in_ring(x, y, hole) for hole in polygon[1:])


def _distance_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class MapUploadService:
    """Parses map uploads into a metric grid; it never trusts client-provided paths or commands."""

    def __init__(self, maximum_cells: int = 4_000_000) -> None:
        self.maximum_cells = maximum_cells

    def ingest(self, path: str | Path) -> MissionMap:
        source = Path(path)
        suffix = source.suffix.lower()
        if suffix in {".geojson", ".json"}:
            return self._geojson(source)
        if suffix == ".pgm":
            return self._pgm(source)
        if suffix in {".tif", ".tiff"}:
            return self._geotiff(source)
        raise ValueError("supported map formats are GeoJSON, PGM and GeoTIFF")

    def _check_size(self, width: int, height: int) -> None:
        if width <= 0 or height <= 0 or width * height > self.maximum_cells:
            raise ValueError(f"map dimensions exceed the {self.maximum_cells} cell development limit")

    def _geojson(self, source: Path) -> MissionMap:
        raw = source.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
            raise ValueError("GeoJSON must be a FeatureCollection")
        properties = payload.get("properties") or {}
        resolution = float(properties.get("resolution_m", 2.0))
        if resolution <= 0:
            raise ValueError("GeoJSON resolution_m must be positive")
        coordinate_mode = str(properties.get("coordinate_system", "LOCAL_ENU")).upper()
        raw_points = list(self._all_geojson_points(payload["features"]))
        if not raw_points:
            raise ValueError("GeoJSON contains no supported coordinates")
        if coordinate_mode in {"WGS84", "EPSG:4326"}:
            origin_lon = float(properties.get("origin_longitude_deg", raw_points[0][0]))
            origin_lat = float(properties.get("origin_latitude_deg", raw_points[0][1]))
            transform = lambda point: self._wgs84_to_local(point[0], point[1], origin_lon, origin_lat)
            coordinate_system = CoordinateSystem.WGS84_PROJECTED
        else:
            transform = lambda point: (float(point[0]), float(point[1]))
            coordinate_system = CoordinateSystem.LOCAL_ENU
        transformed_points = [transform(point) for point in raw_points]
        margin = float(properties.get("margin_m", 5.0))
        origin_x = float(properties.get("origin_x_m", min(point[0] for point in transformed_points) - margin))
        origin_y = float(properties.get("origin_y_m", min(point[1] for point in transformed_points) - margin))
        width = int(properties.get("width_cells", math.ceil((max(p[0] for p in transformed_points) + margin - origin_x) / resolution) + 1))
        height = int(properties.get("height_cells", math.ceil((max(p[1] for p in transformed_points) + margin - origin_y) / resolution) + 1))
        self._check_size(width, height)

        polygons: list[tuple[str, list[list[tuple[float, float]]], float]] = []
        lines: list[tuple[str, list[tuple[float, float]], float, float]] = []
        for feature in payload["features"]:
            geometry = feature.get("geometry") or {}
            props = feature.get("properties") or {}
            layer = str(props.get("layer", props.get("role", "obstacle"))).lower()
            risk_value = max(0.0, min(1.0, float(props.get("risk", 0.7))))
            geometry_type = geometry.get("type")
            coords = geometry.get("coordinates")
            if geometry_type == "Polygon":
                polygons.append((layer, [[transform(tuple(point[:2])) for point in ring] for ring in coords], risk_value))
            elif geometry_type == "MultiPolygon":
                for polygon in coords:
                    polygons.append((layer, [[transform(tuple(point[:2])) for point in ring] for ring in polygon], risk_value))
            elif geometry_type == "LineString":
                line = [transform(tuple(point[:2])) for point in coords]
                lines.append((layer, line, float(props.get("width_m", resolution)), risk_value))
            elif geometry_type == "Point":
                center = transform(tuple(coords[:2]))
                radius = float(props.get("radius_m", resolution))
                lines.append((layer, [center, center], radius, risk_value))

        occupancy = bytearray(width * height)
        risk = [0.0] * (width * height)
        geofences = [polygon for layer, polygon, _ in polygons if layer == "geofence"]
        for y_cell in range(height):
            y_m = origin_y + y_cell * resolution
            for x_cell in range(width):
                x_m = origin_x + x_cell * resolution
                index = y_cell * width + x_cell
                if geofences and not any(_point_in_polygon(x_m, y_m, polygon) for polygon in geofences):
                    occupancy[index] = 1
                    risk[index] = 1.0
                    continue
                for layer, polygon, value in polygons:
                    if layer == "geofence" or not _point_in_polygon(x_m, y_m, polygon):
                        continue
                    if layer in {"obstacle", "restricted", "no_fly", "nofly"}:
                        occupancy[index] = 1
                        risk[index] = 1.0
                    elif layer == "risk":
                        risk[index] = max(risk[index], value)
                    elif layer == "landing_zone":
                        risk[index] = min(risk[index], 0.05)
                for layer, line, width_m, value in lines:
                    if any(_distance_to_segment(x_m, y_m, *start, *end) <= width_m / 2 for start, end in zip(line, line[1:])):
                        if layer in {"obstacle", "restricted", "no_fly", "nofly"}:
                            occupancy[index] = 1
                            risk[index] = 1.0
                        elif layer in {"risk", "corridor"}:
                            risk[index] = max(risk[index], value)
        return MissionMap(
            str(uuid4()), source.name, MapFormat.GEOJSON, _sha256(raw), len(raw), coordinate_system,
            width, height, resolution, origin_x, origin_y, bytes(occupancy), tuple(risk), None,
        )

    @staticmethod
    def _all_geojson_points(features: list[dict[str, Any]]) -> Iterable[tuple[float, float]]:
        def walk(value: Any):
            if isinstance(value, list) and len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
                yield float(value[0]), float(value[1])
            elif isinstance(value, list):
                for child in value:
                    yield from walk(child)

        for feature in features:
            yield from walk((feature.get("geometry") or {}).get("coordinates"))

    @staticmethod
    def _wgs84_to_local(lon: float, lat: float, origin_lon: float, origin_lat: float) -> tuple[float, float]:
        radius = 6_378_137.0
        x = math.radians(lon - origin_lon) * radius * math.cos(math.radians(origin_lat))
        y = math.radians(lat - origin_lat) * radius
        return x, y

    def _pgm(self, source: Path) -> MissionMap:
        raw = source.read_bytes()
        magic, width, height, maximum, pixels = self._decode_pgm(raw)
        self._check_size(width, height)
        metadata_path = source.with_suffix(".yaml")
        if not metadata_path.exists():
            metadata_path = source.with_suffix(".yml")
        metadata = self._simple_yaml(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
        resolution = float(metadata.get("resolution", 1.0))
        origin = metadata.get("origin", [0.0, 0.0, 0.0])
        occupied_threshold = float(metadata.get("occupied_thresh", 0.65))
        free_threshold = float(metadata.get("free_thresh", 0.196))
        negate = bool(int(metadata.get("negate", 0)))
        occupancy = bytearray(width * height)
        risk: list[float] = [0.0] * (width * height)
        for source_y in range(height):
            target_y = height - source_y - 1
            for x in range(width):
                value = pixels[source_y * width + x] / maximum
                probability = value if negate else 1.0 - value
                target_index = target_y * width + x
                if probability >= occupied_threshold:
                    occupancy[target_index], risk[target_index] = 1, 1.0
                elif probability <= free_threshold:
                    occupancy[target_index], risk[target_index] = 0, 0.0
                else:
                    occupancy[target_index], risk[target_index] = 2, 0.5
        return MissionMap(
            str(uuid4()), source.name, MapFormat.PGM, _sha256(raw), len(raw), CoordinateSystem.LOCAL_ENU,
            width, height, resolution, float(origin[0]), float(origin[1]), bytes(occupancy), tuple(risk), None,
        )

    @staticmethod
    def _decode_pgm(raw: bytes) -> tuple[str, int, int, int, list[int]]:
        position = 0

        def token() -> bytes:
            nonlocal position
            while position < len(raw):
                if raw[position:position + 1] == b"#":
                    position = raw.find(b"\n", position)
                    if position < 0:
                        raise ValueError("invalid PGM comment")
                elif raw[position:position + 1].isspace():
                    position += 1
                else:
                    break
            start = position
            while position < len(raw) and not raw[position:position + 1].isspace():
                position += 1
            return raw[start:position]

        magic = token().decode("ascii")
        width, height, maximum = int(token()), int(token()), int(token())
        if magic not in {"P2", "P5"} or maximum <= 0 or maximum > 255:
            raise ValueError("only 8-bit P2/P5 PGM is supported")
        count = width * height
        if magic == "P2":
            pixels = [int(token()) for _ in range(count)]
        else:
            if position >= len(raw) or not raw[position:position + 1].isspace():
                raise ValueError("PGM header is missing its binary separator")
            if raw[position:position + 2] == b"\r\n":
                position += 2
            else:
                position += 1
            pixels = list(raw[position:position + count])
            if len(pixels) != count:
                raise ValueError("truncated PGM pixel data")
        return magic, width, height, maximum, pixels

    @staticmethod
    def _simple_yaml(text: str) -> dict[str, Any]:
        """Parse the strict subset of YAML produced by ROS map_server.

        We intentionally avoid a heavy PyYAML dependency for development use
        while handling: bracketed inline lists ``[...]``, integers, floats,
        quoted or bare strings, booleans and ``negate`` style 0/1 flags.  Keys
        containing ``:`` are not supported because map metadata never uses them.
        """
        result: dict[str, Any] = {}
        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].rstrip()
            if not line.strip() or ":" not in line:
                continue
            # Skip over-indented continuation lines (e.g. nested mappings)
            # that the simple parser cannot represent.
            if line[0] in (" ", "\t"):
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            if not key:
                continue
            if not value:
                result[key] = None
                continue
            # Inline YAML/JSON list
            if value.startswith("[") and value.endswith("]"):
                try:
                    result[key] = json.loads(value)
                    continue
                except json.JSONDecodeError:
                    pass
            # Quoted string
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                result[key] = value[1:-1]
                continue
            lower = value.lower()
            if lower in {"true", "yes", "on"}:
                result[key] = True
                continue
            if lower in {"false", "no", "off"}:
                result[key] = False
                continue
            if lower in {"null", "~", ""}:
                result[key] = None
                continue
            if re.fullmatch(r"[-+]?\d+", value):
                result[key] = int(value)
                continue
            try:
                result[key] = float(value)
            except ValueError:
                result[key] = value
        return result

    def _geotiff(self, source: Path) -> MissionMap:
        try:
            import rasterio
        except ImportError as exc:
            raise RuntimeError("GeoTIFF requires the maps extra: pip install -e '.[maps]'") from exc
        raw = source.read_bytes()
        with rasterio.open(source) as dataset:
            if dataset.crs and dataset.crs.is_geographic:
                raise ValueError("GeoTIFF must be reprojected to a local metric CRS before planning")
            width, height = dataset.width, dataset.height
            self._check_size(width, height)
            band = dataset.read(1, masked=True)
            flipped = band[::-1, :]
            occupancy = bytearray(width * height)
            elevation: list[float] = []
            for index, value in enumerate(flipped.flatten()):
                if getattr(value, "mask", False):
                    occupancy[index] = 2
                    elevation.append(0.0)
                else:
                    elevation.append(float(value))
            resolution = float((abs(dataset.transform.a) + abs(dataset.transform.e)) / 2)
            origin_x, origin_y = float(dataset.bounds.left), float(dataset.bounds.bottom)
        return MissionMap(
            str(uuid4()), source.name, MapFormat.GEOTIFF, _sha256(raw), len(raw), CoordinateSystem.LOCAL_ENU,
            width, height, resolution, origin_x, origin_y, bytes(occupancy),
            tuple(0.5 if value == 2 else 0.0 for value in occupancy), tuple(elevation),
        )


class MapAnalyzer:
    def analyze(self, mission_map: MissionMap) -> MapAnalysis:
        occupied = mission_map.occupancy.count(1)
        unknown = mission_map.occupancy.count(2)
        free = len(mission_map.occupancy) - occupied - unknown
        components, largest = self._components(mission_map)
        warnings: list[str] = []
        total = len(mission_map.occupancy)
        density = occupied / total
        if unknown / total > 0.05:
            warnings.append("more than 5% of map cells are unknown")
        if density > 0.40:
            warnings.append("obstacle density is high")
        if components > 5:
            warnings.append("free space is fragmented")
        if free == 0:
            warnings.append("map has no known free cell")
            status = MapStatus.INVALID
        elif unknown / total > 0.10 or density > 0.60 or components > 10:
            status = MapStatus.DEGRADED
        else:
            status = MapStatus.VALID
        elevations = [
            value for index, value in enumerate(mission_map.elevation_m or ())
            if mission_map.occupancy[index] != 2 and math.isfinite(value)
        ]
        return MapAnalysis(
            occupied, free, unknown, density, components, largest,
            min(elevations) if elevations else None,
            max(elevations) if elevations else None,
            status, tuple(warnings),
        )

    @staticmethod
    def _components(mission_map: MissionMap) -> tuple[int, int]:
        visited = bytearray(mission_map.width_cells * mission_map.height_cells)
        components = 0
        largest = 0
        for index, occupancy in enumerate(mission_map.occupancy):
            if occupancy != 0 or visited[index]:
                continue
            components += 1
            size = 0
            queue = deque([(index % mission_map.width_cells, index // mission_map.width_cells)])
            visited[index] = 1
            while queue:
                x, y = queue.popleft()
                size += 1
                for neighbour in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if not mission_map.contains(neighbour):
                        continue
                    neighbour_index = neighbour[1] * mission_map.width_cells + neighbour[0]
                    if not visited[neighbour_index] and mission_map.occupancy[neighbour_index] == 0:
                        visited[neighbour_index] = 1
                        queue.append(neighbour)
            largest = max(largest, size)
        return components, largest
