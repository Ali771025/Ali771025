from __future__ import annotations
import cv2
import numpy as np
from typing import List

# COCO colors + distinct
PALETTE = [
    (255,0,0),(0,255,0),(0,0,255),(255,255,0),(255,0,255),(0,255,255),
    (128,0,128),(255,128,0),(0,128,255),(128,255,0),(255,0,128),(0,255,128),
    (128,128,0),(128,0,0),(0,128,0),(0,0,128)
]

def get_color(idx: int):
    return PALETTE[idx % len(PALETTE)]

def draw_detections(frame: np.ndarray, detections: List, draw_config=None, class_names=None) -> np.ndarray:
    if draw_config is None:
        from types import SimpleNamespace
        draw_config = SimpleNamespace(labels=True, conf=True, track_id=True, center=False, box_coords=False, line_thickness=2, font_scale=0.5)
    for det in detections:
        x1,y1,x2,y2 = map(int, det.xyxy)
        color = get_color(det.class_id)
        thickness = getattr(draw_config, 'line_thickness', 2)
        cv2.rectangle(frame, (x1,y1), (x2,y2), color, thickness)
        label_parts = []
        if class_names and det.class_id < len(class_names):
            cname = class_names[det.class_id]
        else:
            cname = getattr(det, 'class_name', str(det.class_id))
        if getattr(draw_config,'labels',True):
            label_parts.append(cname)
        if getattr(draw_config,'conf',True):
            label_parts.append(f"{det.confidence*100:.1f}%")
        if getattr(draw_config,'track_id',True) and getattr(det,'track_id',None) is not None and det.track_id != -1:
            label_parts.append(f"ID:{det.track_id}")
        label = " ".join(label_parts)
        if label:
            (tw,th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, draw_config.font_scale, 1)
            cv2.rectangle(frame, (x1, y1-th-baseline-4), (x1+tw+4, y1), color, -1)
            cv2.putText(frame, label, (x1+2, y1-4), cv2.FONT_HERSHEY_SIMPLEX, draw_config.font_scale, (255,255,255), 1, cv2.LINE_AA)
        if getattr(draw_config,'center',False):
            cx,cy = int(det.center[0]), int(det.center[1])
            cv2.circle(frame, (cx,cy), 3, color, -1)
        if getattr(draw_config,'box_coords',False):
            coord_txt = f"{x1},{y1},{x2},{y2}"
            cv2.putText(frame, coord_txt, (x1, y2+15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
    return frame

def draw_overlay(frame: np.ndarray, fps: float, inf_fps: float, source_info: str, model_info: str, device_info: str, count: int, latency_ms: float, conf_thres: float, iou_thres: float, resolution: str):
    h,w = frame.shape[:2]
    overlay_text = [
        f"FPS: {fps:.1f} | INF: {inf_fps:.1f} | Lat: {latency_ms:.1f}ms",
        f"SRC: {source_info} | {resolution}",
        f"MODEL: {model_info} | DEV: {device_info} | CONF:{conf_thres:.2f} IOU:{iou_thres:.2f}",
        f"DETS: {count}"
    ]
    # background
    panel_h = 20+len(overlay_text)*20
    cv2.rectangle(frame, (0,0), (w, panel_h), (0,0,0), -1)
    cv2.rectangle(frame, (0,0), (w, panel_h), (50,50,50), 1)
    y=15
    for txt in overlay_text:
        cv2.putText(frame, txt, (10,y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1, cv2.LINE_AA)
        y+=20
    return frame
