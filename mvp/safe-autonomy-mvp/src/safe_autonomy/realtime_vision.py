from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .database import Database
from .gstreamer_io import GStreamerCamera, GStreamerFramePublisher, NullFramePublisher, StreamEnded
from .multimodal_sync import MultimodalSynchronizer, SynchronizationPolicy
from .tracking import OverlayRenderer, UltralyticsByteTrackBackend
from .vision_contracts import HealthStatus, ModuleHealth, ProcessedFrame
from .vision_repository import VisionRepository
from .wiring import load_wiring, validate_wiring
from .resources import resolve_resource


def _render_template(template: str, values: dict[str, object]) -> str:
    try:
        return template.format_map(values)
    except KeyError as exc:
        raise ValueError(f"missing pipeline parameter: {exc.args[0]}") from exc


def run_realtime(args) -> dict[str, object]:
    if args.health_every <= 0:
        raise ValueError("health_every must be positive")
    config = json.loads(resolve_resource(args.config, "safe_autonomy_config").read_text(encoding="utf-8"))
    profile = config["profiles"].get(args.profile)
    if profile is None:
        raise ValueError(f"unknown camera profile: {args.profile}")
    output_profile = config["outputs"].get(args.output)
    if output_profile is None:
        raise ValueError(f"unknown output profile: {args.output}")
    values = {
        "device": args.device,
        "uri": args.uri,
        "host": args.publish_host,
        "port": args.publish_port,
        "publish_uri": args.publish_uri,
        "width": int(profile["width_px"]),
        "height": int(profile["height_px"]),
        "fps_num": int(profile["fps_num"]),
        "fps_den": int(profile.get("fps_den", 1)),
        "bitrate": args.bitrate,
        "bitrate_kbps": max(1, args.bitrate // 1000),
    }
    input_pipeline = _render_template(str(profile["pipeline"]), values)
    output_pipeline = _render_template(str(output_profile.get("pipeline", "")), values) or None
    wiring = load_wiring(args.wiring)
    wiring_problems = validate_wiring(wiring)
    if wiring_problems:
        raise RuntimeError("invalid system wiring: " + "; ".join(wiring_problems))
    tracker = UltralyticsByteTrackBackend(
        args.model, args.confidence,
        {item.strip() for item in args.classes.split(",") if item.strip()} or None,
        args.tracker,
    )

    database = Database(args.database)
    database.migrate()
    repository = VisionRepository(database)
    repository.save_wiring_revision(wiring, True, ())
    stream_id = repository.start_stream(
        name=args.profile,
        source_type=str(profile["source_type"]),
        input_pipeline=input_pipeline,
        output_pipeline=output_pipeline,
        width_px=values["width"],
        height_px=values["height"],
        fps=values["fps_num"] / values["fps_den"],
        pixel_format="BGR",
        tracker_backend="ultralytics-bytetrack",
        model_version=tracker.model_version,
        configuration={"profile": args.profile, "output": args.output, "max_sync_skew_ms": args.max_sync_skew_ms},
    )
    camera = None
    publisher = None
    processed_count = 0
    failure: str | None = None
    try:
        camera = GStreamerCamera(input_pipeline, stream_id)
        overlay = OverlayRenderer(args.trail_length)
        publisher = (
            GStreamerFramePublisher(output_pipeline, values["fps_num"] / values["fps_den"])
            if output_pipeline else NullFramePublisher()
        )
        synchronizer = MultimodalSynchronizer(database, SynchronizationPolicy(args.max_sync_skew_ms))
        camera.start()
        publisher.start()
        while args.max_frames <= 0 or processed_count < args.max_frames:
            captured = camera.read(args.timeout_s)
            inference_started = time.perf_counter_ns()
            objects = tracker.track(captured.image)
            inference_ms = (time.perf_counter_ns() - inference_started) / 1_000_000
            annotated = overlay.render(captured.image, objects, inference_ms, captured.dropped_before)
            publish_started = time.perf_counter_ns()
            publisher.publish(annotated, captured.metadata)
            publish_ms = (time.perf_counter_ns() - publish_started) / 1_000_000
            end_to_end_ms = max(0.0, time.monotonic_ns() / 1_000_000 - captured.metadata.host_monotonic_ms)
            processed = ProcessedFrame(captured, objects, inference_ms, publish_ms, end_to_end_ms, annotated)
            sync = synchronizer.match(captured.metadata)
            repository.save_processed_frame(processed, sync)
            processed_count += 1
            if processed_count == 1 or processed_count % args.health_every == 0:
                status = HealthStatus.HEALTHY if end_to_end_ms <= args.latency_budget_ms else HealthStatus.DEGRADED
                repository.save_health(ModuleHealth(
                    "realtime_vision", status, time.monotonic_ns() // 1_000_000,
                    end_to_end_ms, len(camera.frames), camera.frames.dropped_count,
                    {"objects": len(objects), "sync_status": sync.status.value},
                ))
    except (KeyboardInterrupt, StreamEnded):
        pass
    except Exception as exc:
        failure = str(exc)
        repository.save_health(ModuleHealth(
            "realtime_vision", HealthStatus.FAILED, time.monotonic_ns() // 1_000_000,
            details={"error": failure},
        ))
        raise
    finally:
        if publisher is not None:
            publisher.stop()
        if camera is not None:
            camera.stop()
        repository.finish_stream(stream_id, failure)
        database.close()
    return {"stream_id": stream_id, "processed_frames": processed_count, "status": "STOPPED"}


def main() -> None:
    parser = argparse.ArgumentParser(description="GStreamer + YOLO ByteTrack realtime vision pipeline")
    parser.add_argument("--config", default="config/camera.gstreamer.dev.json")
    parser.add_argument("--wiring", default="config/system.wiring.json")
    parser.add_argument("--database", default="artifacts/vision_dev_v0.4.sqlite3")
    parser.add_argument("--profile", default="usb_uvc_1080p10")
    parser.add_argument("--output", default="null")
    parser.add_argument("--device", default="/dev/video1")
    parser.add_argument("--uri", default="rtsp://127.0.0.1:8554/input")
    parser.add_argument("--publish-host", default="127.0.0.1")
    parser.add_argument("--publish-port", type=int, default=5600)
    parser.add_argument("--publish-uri", default="rtsp://127.0.0.1:8554/annotated")
    parser.add_argument("--bitrate", type=int, default=10_000_000)
    parser.add_argument("--model", required=True, help="Existing local YOLO .pt model")
    parser.add_argument("--tracker", default="bytetrack.yaml")
    parser.add_argument("--confidence", type=float, default=0.30)
    parser.add_argument("--classes", default="", help="Optional comma-separated class allowlist")
    parser.add_argument("--trail-length", type=int, default=30)
    parser.add_argument("--max-sync-skew-ms", type=int, default=50)
    parser.add_argument("--latency-budget-ms", type=float, default=150.0)
    parser.add_argument("--health-every", type=int, default=30)
    parser.add_argument("--timeout-s", type=float, default=2.0)
    parser.add_argument("--max-frames", type=int, default=0, help="0 means run until interrupted")
    args = parser.parse_args()
    print(json.dumps(run_realtime(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
