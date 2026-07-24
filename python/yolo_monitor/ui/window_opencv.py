from __future__ import annotations
import time
import cv2
import numpy as np
from typing import Optional, List
from ..utils.drawing import draw_detections, draw_overlay
from ..pipeline.types import InferencePacket
from ..config import AppConfig
from ..detectors.base import Detection
from ..utils.fps import FPSCounter

class OpenCVMonitorWindow:
    def __init__(self, config: AppConfig, class_names: List[str] = None):
        self.config = config
        self.class_names = class_names or []
        self.fps_counter = FPSCounter(window=30)
        self.inf_fps = FPSCounter(window=30)
        self.window_name = f"YOLO Monitor - {config.model.path} - {config.source}"
        self.paused = False
        self.show_labels = config.output.draw.labels
        self.show_conf = config.output.draw.conf
        self.show_track = config.output.draw.track_id
        self.show_center = config.output.draw.center
        self.show_coords = config.output.draw.box_coords
        self.show_fps_overlay = config.output.draw.fps_overlay
        self.conf_thres = config.conf_thres
        self.iou_thres = config.iou_thres
        self.recording = False
        self.snapshot_dir = "snapshots"
        self.frame_count = 0

    def draw(self, frame: np.ndarray, result, latency_ms: float, source_status: str, fps: float, inf_fps: float):
        self.frame_count+=1
        # draw boxes
        class DrawCfg:
            labels=self.show_labels
            conf=self.show_conf
            track_id=self.show_track
            center=self.show_center
            box_coords=self.show_coords
            line_thickness=self.config.output.draw.line_thickness
            font_scale=self.config.output.draw.font_scale
        draw_detections(frame, result.detections if result else [], draw_config=DrawCfg(), class_names=self.class_names)
        if self.show_fps_overlay:
            h,w = frame.shape[:2]
            draw_overlay(frame, fps, inf_fps, f"{self.config.source_type}:{source_status}", self.config.model.path, self.config.device, len(result.detections) if result else 0, latency_ms, self.conf_thres, self.iou_thres, f"{w}x{h}")
        return frame

    def handle_keys(self, key: int) -> str:
        # returns action: quit, pause, snapshot, record, toggle etc
        if key == 27 or key == ord('q'):
            return "quit"
        elif key == ord('p'):
            self.paused = not self.paused
            return "pause" if self.paused else "resume"
        elif key == ord('s'):
            return "snapshot"
        elif key == ord('r'):
            self.recording = not self.recording
            return "record_toggle"
        elif key == ord('l'):
            self.show_labels = not self.show_labels
            return "toggle_labels"
        elif key == ord('c'):
            self.show_conf = not self.show_conf
            return "toggle_conf"
        elif key == ord('t'):
            self.show_track = not self.show_track
            return "toggle_track"
        elif key == ord('f'):
            self.show_fps_overlay = not self.show_fps_overlay
            return "toggle_fps"
        elif key == ord('+') or key == ord('='):
            self.conf_thres = min(1.0, self.conf_thres+0.05)
            return "conf_up"
        elif key == ord('-') or key == ord('_'):
            self.conf_thres = max(0.0, self.conf_thres-0.05)
            return "conf_down"
        elif key == ord(']'):
            self.iou_thres = min(1.0, self.iou_thres+0.05)
            return "iou_up"
        elif key == ord('['):
            self.iou_thres = max(0.0, self.iou_thres-0.05)
            return "iou_down"
        return ""

    def show(self, frame: np.ndarray):
        cv2.imshow(self.window_name, frame)

    def close(self):
        try:
            cv2.destroyWindow(self.window_name)
        except Exception:
            cv2.destroyAllWindows()
