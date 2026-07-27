from __future__ import annotations

import argparse
import json
import time

from .database import Database
from .px4_normalizer import Px4MessageNormalizer
from .sensor_contracts import PerceptionObject, SensorKind
from .sensor_fusion import TelemetrySynchronizer
from .telemetry_repository import TelemetryRepository


def run_bridge(args) -> None:
    try:
        import rclpy
        from rclpy.node import Node
        from rclpy.qos import qos_profile_sensor_data
        from px4_msgs.msg import (
            AirspeedValidated,
            BatteryStatus,
            DistanceSensor,
            SensorCombined,
            SensorMag,
            VehicleAirData,
            VehicleGpsPosition,
        )
        from std_msgs.msg import String
    except ImportError as exc:
        raise RuntimeError("ROS 2 Humble, rclpy, px4_msgs and std_msgs must be installed in the ROS workspace") from exc

    database = Database(args.database)
    database.migrate()
    repository = TelemetryRepository(database)
    synchronizer = TelemetrySynchronizer(args.home_lat, args.home_lon, args.home_alt)
    normalizer = Px4MessageNormalizer()

    class ReadOnlyTelemetryNode(Node):
        def __init__(self) -> None:
            super().__init__("safe_autonomy_read_only_telemetry")
            qos = qos_profile_sensor_data
            self.create_subscription(VehicleGpsPosition, "/fmu/out/vehicle_gps_position", lambda msg: self.update(SensorKind.GPS, normalizer.gps(msg)), qos)
            self.create_subscription(SensorCombined, "/fmu/out/sensor_combined", lambda msg: self.update(SensorKind.IMU, normalizer.imu(msg)), qos)
            self.create_subscription(VehicleAirData, "/fmu/out/vehicle_air_data", lambda msg: self.update(SensorKind.BAROMETER, normalizer.barometer(msg)), qos)
            self.create_subscription(SensorMag, "/fmu/out/sensor_mag", lambda msg: self.update(SensorKind.MAGNETOMETER, normalizer.magnetometer(msg)), qos)
            self.create_subscription(AirspeedValidated, "/fmu/out/airspeed_validated", lambda msg: self.update(SensorKind.AIRSPEED, normalizer.airspeed(msg)), qos)
            self.create_subscription(DistanceSensor, "/fmu/out/distance_sensor", lambda msg: self.update(SensorKind.RANGEFINDER, normalizer.rangefinder(msg)), qos)
            self.create_subscription(BatteryStatus, "/fmu/out/battery_status", lambda msg: self.update(SensorKind.BATTERY, normalizer.battery(msg)), qos)
            self.create_subscription(String, "/safe_autonomy/perception_json", self.on_perception, qos)
            self.create_timer(0.1, self.persist_frame)

        def update(self, kind, sample) -> None:
            synchronizer.update(kind, sample)
            repository.save_sample(kind, sample)

        def on_perception(self, message) -> None:
            payload = json.loads(message.data)
            objects = tuple(PerceptionObject(
                object_id=str(item["object_id"]), class_name=str(item["class_name"]),
                confidence=float(item["confidence"]), timestamp_ms=int(item["timestamp_ms"]),
                bbox_xyxy_px=tuple(float(value) for value in item["bbox_xyxy_px"]),
                track_id=item.get("track_id"), depth_m=item.get("depth_m"),
                depth_variance_m2=item.get("depth_variance_m2"),
                relative_velocity_mps=item.get("relative_velocity_mps"), ttc_s=item.get("ttc_s"),
            ) for item in payload.get("objects", []))
            synchronizer.update_perception(objects)

        def persist_frame(self) -> None:
            samples = synchronizer.samples()
            if not samples:
                return
            now_ms = max(sample.header.timestamp_ms for _, sample in samples)
            try:
                frame = synchronizer.snapshot(now_ms, time.monotonic_ns() // 1_000_000)
            except RuntimeError:
                return
            repository.save_frame(frame)

    rclpy.init()
    node = ReadOnlyTelemetryNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        database.close()
        rclpy.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only ROS 2/PX4 telemetry to database bridge")
    parser.add_argument("--database", default="artifacts/telemetry_dev.sqlite3")
    parser.add_argument("--home-lat", type=float, required=True)
    parser.add_argument("--home-lon", type=float, required=True)
    parser.add_argument("--home-alt", type=float, required=True)
    run_bridge(parser.parse_args())


if __name__ == "__main__":
    main()
