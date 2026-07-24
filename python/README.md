# Python Implementation — Offline YOLO Monitor + Annotator + GPU Development

## نصب

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
pip install -e .
pip install PySide6  # GUI

# GPU
pip uninstall onnxruntime -y
pip install onnxruntime-gpu==1.16.3
pip install ultralytics torch torchvision --index-url https://download.pytorch.org/whl/cu121
python scripts/verify_installation.py
python -c "import onnxruntime as ort; print(ort.get_available_providers())"  # باید CUDAExecutionProvider باشد
```

## اجرای Monitor

```bash
# USB CPU
python -m yolo_monitor --source 0 --model ../models/yolov8n.onnx --device cpu --show --log detections.jsonl

# USB GPU
python -m yolo_monitor --source 0 --model ../models/yolov8n.onnx --device cuda --half --show

# RTSP با reconnect
export CAMERA_USER=admin CAMERA_PASSWORD=secret
python -m yolo_monitor --source rtsp://CAMERA_USER:CAMERA_PASSWORD@192.168.1.10/stream --model ../models/yolov8n.onnx --device cuda --show

# Video + save
python -m yolo_monitor --source video.mp4 --model ../models/yolov8n.onnx --conf 0.35 --save-video out.mp4 --log out.jsonl --log-format both

# Images batch
python -m yolo_monitor --source ../datasets/images --source-type images --model ../models/yolov8n.onnx --show

# GStreamer
python -m yolo_monitor --source "v4l2src device=/dev/video0 ! videoconvert ! appsink" --source-type gstreamer --model ../models/yolov8n.onnx --show

# Config YAML
python -m yolo_monitor --config ../configs/default.yaml --offline
```

## تست و بنچمارک

```bash
pytest tests -v
python ../scripts/benchmark.py --model ../models/yolov8n.onnx --device cpu --iters 100
python ../scripts/benchmark.py --model ../models/yolov8n.onnx --device cuda --iters 100 --source video.mp4
```

## توسعه GPU

- `detectors/onnx_detector.py`: `SessionOptions` + `CUDAExecutionProvider`, half support
- `detectors/ultralytics_detector.py`: `device` param به `model.predict(device=...)`
- بهینه‌سازی: letterbox, FP16, bounded queue, async logging, frame_skip
- برای توسعه: `device="cuda:0"`, `half=True`, `imgsz=416`, `batch_size` آینده

## Annotator قدیمی

```bash
python -m yolo_annotator --project ../datasets/my_dataset --model ../models/yolov8n.onnx --offline
python -m yolo_annotator --project ../datasets/my --model ../models/yolov8n.onnx --headless --images data/ --export-format yolo --export-path export/
```

## عیب‌یابی GPU

- CUDAExecutionProvider not found → onnxruntime-gpu نصب کن
- Low FPS → yolo11n + imgsz 416 + frame_skip 1
- RTSP lag → OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp
