# C++ Usage

Build first:

```bash
cmake -S cpp -B build -DCMAKE_BUILD_TYPE=Release -DYOLO_WITH_QT=ON -DYOLO_WITH_ONNXRUNTIME=ON
cmake --build build -j
```

Run:

```bash
# USB
./build/yolo_app --source 0 --model models/yolov8n.onnx --device cpu --show --log out.csv

# RTSP
export CAMERA_USER=admin
export CAMERA_PASSWORD=secret
./build/yolo_app --source rtsp://CAMERA_USER:CAMERA_PASSWORD@192.168.1.10/stream --model models/yolov8n.onnx --device cuda --show --log out.jsonl

# Video file
./build/yolo_app --source video.mp4 --model models/yolov8n.onnx --conf 0.35 --iou 0.45 --save-video out.mp4 --log det.jsonl

# Image folder
./build/yolo_app --source datasets/images --model models/yolov8n.onnx --log out.csv

# With config YAML
./build/yolo_app --config configs/default.yaml
```

## GUI Monitoring

If Qt6 enabled:

```bash
./build/yolo_gui --source 0 --model models/yolov8n.onnx --device cpu
```

Shows live window with FPS overlay.

## Annotator

```bash
# GUI
./build/yolo_annotator --project datasets/my_dataset --model models/yolov8n.onnx

# Headless auto-label + export
./build/yolo_annotator --project datasets/my_dataset --model models/yolov8n.onnx --images data/images --export-format yolo --export-path export/ --headless
```

## Logging

- `--log out.csv` => CSV
- `--log out.jsonl` => JSON Lines
- `--log-format both` => writes both
- Secret masking enforced - password not printed.

## Benchmark

Use Python benchmark script, or run with verbose logging to see FPS.

## Optimizations

- OpenCV DNN backend will try CUDA if device=cuda and OpenCV built with CUDA
- ONNX Runtime with CUDAExecutionProvider if available
- TensorRT engine loading if built with TensorRT
- Bounded queues, frame dropping, no unnecessary copies

## API

Library `yolo_core` provides:

- `create_source(source, type, timeout)`
- `create_detector(model, backend, device, ...)`
- `DetectionPipeline(config)`
- `LogWriter`
- `AutoLabeler` (annotator_core)
- Project import/export

Use in your own C++ app:

```cpp
#include "yolo/detector/detector_factory.h"
#include "yolo/source/factory.h"
auto det = yolo::create_detector("models/yolov8n.onnx", "onnx", "cuda", 640, 0.35, 0.45);
det->load();
cv::Mat frame = ...;
auto res = det->detect(frame);
```
