#!/usr/bin/env python3
"""Send realistic development telemetry to the dashboard UDP/TCP ingest ports."""
from __future__ import annotations

import argparse
import json
import math
import socket
import time
import uuid
import zlib


def envelope(topic: str, source: str, sequence: int, payload: dict) -> bytes:
    data = {
        "schema_version": "1.0",
        "message_id": str(uuid.uuid4()),
        "topic": topic,
        "source": source,
        "sequence_no": sequence,
        "sent_at_ms": int(time.time() * 1000),
        "host_monotonic_ms": int(time.monotonic() * 1000),
        "payload": payload,
    }
    unsigned = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    data["crc32"] = f"{zlib.crc32(unsigned) & 0xFFFFFFFF:08x}"
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()


def reliable(sock: socket.socket, topic: str, seq: int, payload: dict) -> None:
    sock.sendall(envelope(topic, "fixture-core", seq, payload) + b"\n")
    sock.recv(256)


def run(host: str, udp_port: int, tcp_port: int, hz: float, fault_after: float | None) -> None:
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tcp = socket.create_connection((host, tcp_port), timeout=3)
    tcp.settimeout(1)
    start = time.monotonic()
    seq = 0
    slow_seq = 0
    alert_sent = False
    interval = 1 / hz
    print(f"fixture -> udp://{host}:{udp_port} @ {hz:g}Hz, tcp://{host}:{tcp_port}")
    try:
        while True:
            tick = time.monotonic()
            elapsed = tick - start
            fault = fault_after is not None and elapsed >= fault_after
            battery = max(8, 88 - elapsed * (1.2 if fault else .08))
            progress = min(100, elapsed * 1.4)
            telemetry = {
                "latitude": 35.7041 + math.sin(elapsed / 30) * .003,
                "longitude": 51.3512 + math.cos(elapsed / 32) * .004,
                "altitude_m": 1280 + 48 + math.sin(elapsed / 4) * 3,
                "relative_altitude_m": 48 + math.sin(elapsed / 4) * 3,
                "groundspeed_mps": 13.2 + math.sin(elapsed / 3) * 1.7,
                "vertical_speed_mps": math.cos(elapsed / 4) * .7,
                "heading_deg": (74 + elapsed * 1.7) % 360,
                "roll_deg": math.sin(elapsed * 1.4) * 3.4,
                "pitch_deg": math.cos(elapsed) * 2.1,
                "yaw_deg": (74 + elapsed * 1.7) % 360,
                "battery_percent": battery,
                "battery_voltage_v": 24.8 * battery / 100 + 1.5,
                "gps_fix": 2 if fault else 3,
                "satellites": 7 if fault else 18,
                "link_quality": 18 if fault else 94 + math.sin(elapsed) * 2,
                "ekf_healthy": not fault,
                "armed": True,
                "flight_mode": "AUTO_MISSION" if not fault else "HOLD",
                "mission_progress": progress,
            }
            udp.sendto(envelope("telemetry", "px4-bridge", seq, telemetry), (host, udp_port))
            seq += 1
            if seq % max(1, int(hz / 2)) == 0:
                slow_seq += 1
                vision = {
                    "fps": 29.7,
                    "inference_ms": 18.4,
                    "tracks": [
                        {"id": 31, "label": "vehicle", "confidence": .92, "x": .16 + .05 * math.sin(elapsed), "y": .35, "w": .18, "h": .23},
                        {"id": 44, "label": "person", "confidence": .86, "x": .67, "y": .42 + .03 * math.cos(elapsed), "w": .08, "h": .27},
                    ],
                }
                udp.sendto(envelope("vision", "vision-pipeline", slow_seq, vision), (host, udp_port))
                assessment = {"phase": "HOLD" if fault else "CRUISE", "risk_level": "CRITICAL" if fault else "NOMINAL", "eta_seconds": max(0, 420 - elapsed)}
                udp.sendto(envelope("flight_assessment", "decision-engine", slow_seq, assessment), (host, udp_port))
            if seq % max(1, int(hz * 3)) == 0:
                slow_seq += 1
                reliable(tcp, "module_health", slow_seq, {
                    "GPS": "DEGRADED" if fault else "HEALTHY", "IMU": "HEALTHY", "YOLO": "HEALTHY",
                    "GStreamer": "HEALTHY", "Tracker": "HEALTHY", "RAG": "READY", "Knowledge Graph": "READY",
                })
                reliable(tcp, "route_candidates", slow_seq + 1, {
                    "selected_route_id": "route-primary",
                    "routes": [
                        {"id": "route-primary", "cost": 1.0, "points": [{"x": 4,"y":-25},{"x":22,"y":-17},{"x":39,"y":-10},{"x":58,"y":-3},{"x":79,"y":8},{"x":96,"y":15}]},
                        {"id": "route-alt-a", "cost": 1.18, "points": [{"x":4,"y":-25},{"x":25,"y":-11},{"x":42,"y":2},{"x":69,"y":5},{"x":96,"y":15}]},
                    ],
                })
            if fault and not alert_sent:
                reliable(tcp, "alert", slow_seq + 2, {
                    "id": str(uuid.uuid4()), "severity": "CRITICAL", "code": "NAV_DEGRADED",
                    "title": "افت همزمان GPS و لینک", "detail": "GPS سه‌بعدی و کیفیت لینک از آستانه عملیاتی خارج شده‌اند.",
                })
                alert_sent = True
            delay = interval - (time.monotonic() - tick)
            if delay > 0:
                time.sleep(delay)
    except KeyboardInterrupt:
        print("\nfixture stopped")
    finally:
        udp.close(); tcp.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--udp-port", type=int, default=15010)
    parser.add_argument("--tcp-port", type=int, default=15011)
    parser.add_argument("--hz", type=float, default=20)
    parser.add_argument("--fault-after", type=float, default=None, help="seconds before GPS/link fault")
    args = parser.parse_args()
    run(args.host, args.udp_port, args.tcp_port, args.hz, args.fault_after)

