# Python Usage

## Detection CLI

```bash
# USB webcam (auto-detects 0)
python -m yolo_monitor --source 0 --model models/yolov8n.onnx --device cpu --show --log out.csv

# V4L2 Linux device
python -m yolo_monitor --source /dev/video0 --model models/yolov8n.onnx --device auto --show

# RTSP with env secrets
export CAMERA_USER=admin
export CAMERA_PASSWORD=secret
export RTSP_URL="rtsp://CAMERA_USER:CAMERA_PASSWORD@192.168.1.10:554/stream"
python -m yolo_monitor --source rtsp://CAMERA_USER:CAMERA_PASSWORD@192.168.1.10/stream --model models/yolov8n.onnx --device cuda --show --log det.jsonl

# RTSP direct (password masked in logs)
python -m yolo_monitor --source rtsp://admin:secret@192.168.1.10/stream --model models/yolov8s.onnx --backend onnx --show

# HTTP MJPEG / IP camera
python -m yolo_monitor --source http://192.168.1.11/video --model models/yolov8n.onnx --show

# Video file with save
python -m yolo_monitor --source video.mp4 --model models/yolov8n.onnx --conf 0.35 --iou 0.45 --save-video out.mp4 --log detections.jsonl

# Image folder batch
python -m yolo_monitor --source datasets/images --model models/yolov8n.onnx --show --log batch.jsonl

# GStreamer pipeline
python -m yolo_monitor --source "v4l2src device=/dev/video0 ! videoconvert ! appsink" --source-type gstreamer --model models/yolov8n.onnx --show
```

## Options

- `--source`: 0, /dev/video0, rtsp://..., http://..., video.mp4, folder, gstreamer string
- `--source-type`: auto, usb, v4l2, rtsp, http, video, images, gstreamer
- `--model`: models/yolov8n.onnx, .pt (needs ultralytics), .engine
- `--backend`: auto, onnx, ultralytics, tensorrt
- `--device`: auto, cpu, cuda:0, tensorrt
- `--imgsz`: 640
- `--conf`: 0.35
- `--iou`: 0.45
- `--max-det`: 300
- `--classes`: e.g. "0,2,3"
- `--half`: FP16
- `--show/--no-show`: live window
- `--save-video`: output path
- `--log`: CSV/JSONL path
- `--log-format`: csv, jsonl, both, sqlite
- `--config`: YAML config
- `--offline`: enforce offline
- `--frame-skip`: 0=all frames, 1=every 2nd frame
- `--verbose`

## Config YAML

See `configs/default.yaml`. Example:

```yaml
source: "0"
model:
  path: "models/yolov8n.onnx"
  backend: "onnx"
device: "cuda"
conf_thres: 0.35
iou_thres: 0.45
```

Run with config: `python -m yolo_monitor --config configs/usb_camera.yaml`

## Logging Schema

Each detection row (CSV/JSONL):

- timestamp_unix, timestamp_iso
- source_id (masked), source_type
- frame_id, frame_width, frame_height
- model_name, device/backend
- class_id, class_name, confidence
- x1,y1,x2,y2, x,y,w,h, cx,cy,nw,nh
- center_x, center_y, area, aspect_ratio
- track_id, inference_time_ms, latency_ms

## Performance

```bash
python scripts/benchmark.py --model models/yolov8n.onnx --device cpu --iters 100
python scripts/benchmark.py --model models/yolov8n.onnx --device cuda --iters 100 --source video.mp4
```

- Use `--device cuda` for GPU.
- Use `--half` for FP16 (TensorRT or ONNX).
- Use `--frame-skip 1` for 2x speed on CPU.
- Use smaller model `yolo11n` / `yolov8n`.

## Code structure

- `yolo_monitor/sources`: abstraction for all input types
- `yolo_monitor/detectors`: ONNX, Ultralytics, TensorRT
- `yolo_monitor/pipeline`: threaded pipeline with bounded queues
- `yolo_monitor/ui`: OpenCV + Qt monitoring
- `yolo_monitor/logging`: async CSV/JSONL writer with masking
- `yolo_monitor/tracking`: IoU tracker

## Troubleshooting

See `docs/troubleshooting.md`.
