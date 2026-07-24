# C++ Implementation — Offline YOLO + GPU Development

## Dependencies Ubuntu 22.04

```bash
sudo apt update
sudo apt install -y build-essential cmake ninja-build pkg-config \
  libopencv-dev libspdlog-dev libyaml-cpp-dev nlohmann-json3-dev \
  libcli11-dev qt6-base-dev libgtest-dev

# Optional ONNX Runtime CPU
wget https://github.com/microsoft/onnxruntime/releases/download/v1.16.3/onnxruntime-linux-x64-1.16.3.tgz
tar xzf onnxruntime-linux-x64-1.16.3.tgz
sudo cp -r onnxruntime-linux-x64-1.16.3/include/* /usr/include/
sudo cp -r onnxruntime-linux-x64-1.16.3/lib/* /usr/lib/

# ONNX Runtime GPU
wget https://github.com/microsoft/onnxruntime/releases/download/v1.16.3/onnxruntime-linux-x64-gpu-1.16.3.tgz
tar xzf onnxruntime-linux-x64-gpu-1.16.3.tgz -C /opt
export ONNXRUNTIME_ROOT=/opt/onnxruntime-linux-x64-gpu-1.16.3
```

## Build

```bash
# CPU + Qt
cmake -S cpp -B build -DCMAKE_BUILD_TYPE=Release -DYOLO_WITH_QT=ON -DYOLO_WITH_ONNXRUNTIME=ON
cmake --build build -j

# GPU + TensorRT
cmake -S cpp -B build -DCMAKE_BUILD_TYPE=Release \
  -DYOLO_WITH_QT=ON \
  -DYOLO_WITH_ONNXRUNTIME=ON -DONNXRUNTIME_ROOT=$ONNXRUNTIME_ROOT \
  -DYOLO_WITH_TENSORRT=ON -DYOLO_WITH_CUDA=ON
cmake --build build -j

./build/yolo_tests
```

## Run CPU

```bash
./build/yolo_app --source 0 --model models/yolov8n.onnx --device cpu --show --log out.csv
./build/yolo_app --source video.mp4 --model models/yolov8n.onnx --conf 0.35 --save-video out.mp4 --log det.jsonl
./build/yolo_app --source datasets/images --model models/yolov8n.onnx --log out.csv
./build/yolo_gui --source 0 --model models/yolov8n.onnx --device cpu
./build/yolo_annotator --project datasets/my_dataset --model models/yolov8n.onnx
```

## Run GPU

```bash
# ONNX Runtime CUDA
./build/yolo_app --source 0 --model models/yolov8n.onnx --device cuda --show

# TensorRT engine
python models/export_tensorrt.py --model models/yolov8n.onnx --imgsz 640 --half
./build/yolo_app --source 0 --model models/yolov8n.engine --backend tensorrt --device tensorrt --show

# Check provider
# Log shows: Found ONNX Runtime: ... providers = [CUDAExecutionProvider, CPUExecutionProvider]

# OpenCV DNN CUDA (if OpenCV built with CUDA)
./build/yolo_app --source 0 --model models/yolov8n.onnx --backend opencv --device cuda --show
```

## GPU Development Guide

**OpenCVDNNDetector:**
```cpp
if (device_=="cuda") {
  net.setPreferableBackend(cv::dnn::DNN_BACKEND_CUDA);
  net.setPreferableTarget(cv::dnn::DNN_TARGET_CUDA_FP16);
}
```
Fallback خودکار به CPU اگر CUDA موجود نباشد.

**OnnxDetector:**
```cpp
Ort::SessionOptions opts;
OrtCUDAProviderOptions cuda_opts;
opts.AppendExecutionProvider_CUDA(cuda_opts);
session = Ort::Session(env, model_path, opts);
```

**Optimizations:**
- Preallocated buffers, contiguous memory
- CHW, zero-copy where possible
- BoundedQueue drop-oldest, async logging, frame dropping
- FP16 TensorRT

**Benchmark:**
```bash
# Use Python benchmark script for now, or verbose logs show FPS
./build/yolo_app --source video.mp4 --model models/yolov8n.onnx --device cuda --show
# Log: Frame 30 FPS 32.5 INF 30.1 Dets 2
```

## API

```cpp
#include "yolo/detector/detector_factory.h"
#include "yolo/source/factory.h"
auto det = yolo::create_detector("models/yolov8n.onnx","onnx","cuda",640,0.35,0.45);
det->load();
cv::Mat frame = ...;
auto res = det->detect(frame);
```

## Docker

```bash
docker build -f docker/Dockerfile.cpu -t offline-yolo:cpu .
docker build -f docker/Dockerfile.cuda -t offline-yolo:cuda .
```

## Troubleshooting GPU

- OpenCV not found: sudo apt install libopencv-dev (یا از source با -DWITH_CUDA=ON بساز)
- ONNX Runtime not found: warning می‌دهد و fallback به OpenCV DNN می‌رود, اگر می‌خواهی غیرفعال: -DYOLO_WITH_ONNXRUNTIME=OFF
- TensorRT not found: NvInfer.h پیدا نشد → -DYOLO_WITH_TENSORRT=OFF
- Qt6 not found: qt6-base-dev نصب یا -DYOLO_WITH_QT=OFF
