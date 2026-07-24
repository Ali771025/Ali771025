# offline-yolo-monitor-annotator

Production-grade, fully offline YOLO object detection with parallel Python and C++ implementations, live monitoring, logging/export, and professional AI-assisted annotation.

## Features

- **Offline runtime** - No cloud APIs, telemetry, or internet required at inference time
- **Multi-source** - USB webcams (DirectShow / V4L2), RTSP, HTTP/MJPEG, RTMP, GStreamer pipelines, video files, image folders
- **Dual implementation**
  - Python: ONNX Runtime, optional Ultralytics + TensorRT, PySide6 monitoring UI
  - C++: C++20, ONNX Runtime, TensorRT, OpenCV, Qt6 GUI, spdlog, thread-safe pipeline
- **Live monitoring window** with FPS, source info, model info, detection boxes, interactive controls
- **Full metadata logging** - CSV, JSON Lines, SQLite, pixel + normalized boxes, tracking
- **Professional annotator** - Projects, bbox/polygon, AI auto-label with local YOLO, SAM-assisted segmentation, video frame extraction, YOLO/COCO/VOC export
- **Optimized pipeline** - Capture → Preprocess → Inference → Postprocess → Render → Logging threads, bounded queues, frame dropping, reconnect with backoff

## Quick Start

### Python

```bash
pip install -r python/requirements.txt
python models/download_models.py --yolo yolo11n  # one-time download
python -m yolo_monitor --source 0 --model models/yolov8n.onnx --device cpu --show --log out.csv
python -m yolo_monitor --source video.mp4 --model models/yolov8n.onnx --conf 0.35 --save-video out.mp4 --log det.jsonl
python -m yolo_annotator --project datasets/my_dataset --model models/yolov8n.onnx --offline
```

### C++

```bash
# Ubuntu 22.04
sudo apt install libopencv-dev libonnxruntime-dev libyaml-cpp-dev libspdlog-dev qt6-base-dev
cmake -S cpp -B build -DCMAKE_BUILD_TYPE=Release -DYOLO_WITH_QT=ON -DYOLO_WITH_ONNXRUNTIME=ON
cmake --build build -j
./build/yolo_app --source 0 --model models/yolov8n.onnx --device cpu --show --log out.csv
./build/yolo_annotator --project datasets/my_dataset
```

## Docs

- [Installation](docs/installation.md)
- [Python Usage](docs/python_usage.md)
- [C++ Usage](docs/cpp_usage.md)
- [Annotation Guide](docs/annotation_guide.md)
- [Model Export](docs/model_export.md)
- [Troubleshooting](docs/troubleshooting.md)

## License

MIT
