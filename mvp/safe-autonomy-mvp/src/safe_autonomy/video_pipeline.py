from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .database import AutonomyRepository, Database
from .perception import DetectorBackend, MetadataOnlyBackend, UltralyticsBackend, probe_video, sample_frames


def run_video_pipeline(
    video_path: str | Path,
    database_path: str | Path,
    frames_dir: str | Path,
    backend: DetectorBackend,
    sample_fps: float = 2.0,
) -> dict[str, object]:
    database = Database(database_path)
    database.migrate()
    repository = AutonomyRepository(database)
    started_at_ms = int(time.time() * 1000)
    metadata = probe_video(video_path)
    configuration = dict(backend.configuration)
    configuration["sample_fps"] = sample_fps
    run_id = repository.start_video_run(
        metadata, backend.name, backend.model_version, started_at_ms, configuration,
    )
    try:
        if backend.name != "metadata-only":
            run_frames_dir = Path(frames_dir) / run_id
            for frame in sample_frames(video_path, run_frames_dir, sample_fps, metadata.fps):
                for detection in backend.predict(frame):
                    repository.save_detection(run_id, detection, int(time.time() * 1000))
        repository.finish_video_run(run_id, int(time.time() * 1000))
        return repository.video_run_summary(run_id)
    except Exception as exc:
        repository.finish_video_run(run_id, int(time.time() * 1000), str(exc))
        raise
    finally:
        database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist video metadata and optional YOLO detections")
    parser.add_argument("--video", required=True)
    parser.add_argument("--database", default="artifacts/autonomy_dev.sqlite3")
    parser.add_argument("--frames-dir", default="artifacts/frames")
    parser.add_argument("--backend", choices=("metadata", "ultralytics"), default="metadata")
    parser.add_argument("--model", help="Local YOLO .pt path; required for ultralytics backend")
    parser.add_argument("--sample-fps", type=float, default=2.0)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--classes", default="airplane", help="Comma-separated allowlist")
    args = parser.parse_args()
    if args.backend == "ultralytics":
        if not args.model:
            parser.error("--model is required for ultralytics backend")
        allowed = {item.strip() for item in args.classes.split(",") if item.strip()}
        backend: DetectorBackend = UltralyticsBackend(args.model, args.confidence, allowed)
    else:
        backend = MetadataOnlyBackend()
    summary = run_video_pipeline(args.video, args.database, args.frames_dir, backend, args.sample_fps)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
