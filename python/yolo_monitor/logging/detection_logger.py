from __future__ import annotations
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from ..detectors.base import Detection, FrameResult
from .async_writer import AsyncWriter
from ..utils.secrets import mask_url

class DetectionLogger:
    def __init__(self, log_path: Optional[str], log_format: str = "jsonl", source_id: str = "", source_type: str = "", model_name: str = "", device: str = ""):
        self.log_path = log_path
        self.log_format = log_format
        self.source_id = mask_url(source_id)
        self.source_type = source_type
        self.model_name = model_name
        self.device = device
        self.writer: Optional[AsyncWriter] = None
        if log_path:
            self.writer = AsyncWriter(log_path, format=log_format)
            self.writer.start()
        self.frame_counter = 0

    def log_detections(self, result: FrameResult, latency_ms: float = 0.0):
        if not self.writer:
            return
        ts_unix = result.timestamp_unix or time.time()
        ts_iso = datetime.fromtimestamp(ts_unix, tz=timezone.utc).isoformat()
        for det in result.detections:
            record = {
                "timestamp_unix": ts_unix,
                "timestamp_iso": ts_iso,
                "source_id": self.source_id,
                "source_type": self.source_type,
                "frame_id": result.frame_id,
                "frame_width": result.width,
                "frame_height": result.height,
                "model_name": det.model_name or self.model_name,
                "device": self.device,
                "backend": self.device,
                "class_id": det.class_id,
                "class_name": det.class_name,
                "confidence": det.confidence,
                "x1": det.xyxy[0],
                "y1": det.xyxy[1],
                "x2": det.xyxy[2],
                "y2": det.xyxy[3],
                "x": det.xywh[0],
                "y": det.xywh[1],
                "w": det.xywh[2],
                "h": det.xywh[3],
                "cx": det.xywh_norm[0],
                "cy": det.xywh_norm[1],
                "nw": det.xywh_norm[2],
                "nh": det.xywh_norm[3],
                "center_x": det.center[0],
                "center_y": det.center[1],
                "area": det.area,
                "aspect_ratio": det.aspect_ratio,
                "track_id": det.track_id,
                "inference_time_ms": det.inference_time_ms,
                "latency_ms": latency_ms,
                # compat aliases
                "bbox_xyxy": list(det.xyxy),
                "bbox_xywh": list(det.xywh),
                "bbox_normalized_xywh": list(det.xywh_norm),
            }
            self.writer.write(record)

    def log_frame_summary(self, result: FrameResult, fps: float, source_status: str = "ok", dropped_frames: int = 0):
        if not self.writer:
            return
        # optional per-frame summary if needed
        # here we only log if configured to log per frame? User can handle elsewhere

    def close(self):
        if self.writer:
            self.writer.stop()
