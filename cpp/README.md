# C++ Implementation

## Dependencies

### Ubuntu 22.04

```bash
sudo apt update
sudo apt install -y build-essential cmake ninja-build pkg-config \
  libopencv-dev libspdlog-dev libyaml-cpp-dev nlohmann-json3-dev \
  libcli11-dev qt6-base-dev libgtest-dev
```

## Build

```bash
cmake -S cpp -B build -DCMAKE_BUILD_TYPE=Release -DYOLO_WITH_QT=ON -DYOLO_WITH_ONNXRUNTIME=ON
cmake --build build -j
```

## Run

```bash
./build/yolo_app --source 0 --model models/yolov8n.onnx --device cpu --show --log out.csv
./build/yolo_app --source video.mp4 --model models/yolov8n.onnx --conf 0.35 --iou 0.45 --save-video out.mp4 --log detections.jsonl
./build/yolo_annotator --project datasets/my_dataset
```

## Architecture

- `yolo_core`: config, detection types, bbox utils, detector interface, source abstraction, pipeline, logging
- `yolo_detector`: ONNX Runtime + OpenCV DNN + TensorRT detectors
- `yolo_source`: USB/V4L2/RTSP/HTTP/file/images
- `yolo_pipeline`: threaded capture/inference/render pipeline with bounded queues, reconnect logic
- `yolo_app`: CLI executable
- `yolo_gui`: Qt6 monitoring UI
- `yolo_annotator_core`: annotation project, import/export YOLO/COCO/VOC, AI pre-labeling using yolo_core
- `yolo_annotator_gui`: Qt6 annotation UI

## Offline

Runtime requires no internet. Models cached in ./models.

## Performance

- Preallocated buffers, contiguous memory, zero-copy where possible
- FP16 TensorRT if available
- Thread-safe queues with frame dropping
- Async CSV/JSONL logging with secret masking
