# Installation

## Ubuntu 22.04+

### Python

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r python/requirements.txt

# Optional GPU
pip install onnxruntime-gpu

# Optional Ultralytics
pip install ultralytics torch torchvision

# Optional GUI
pip install PySide6

# Verify
python scripts/verify_installation.py
```

### C++

```bash
sudo apt update
sudo apt install -y build-essential cmake ninja-build pkg-config \
  libopencv-dev libspdlog-dev libyaml-cpp-dev nlohmann-json3-dev \
  libcli11-dev qt6-base-dev libgtest-dev

# Optional ONNX Runtime CPU
# Download from https://github.com/microsoft/onnxruntime/releases
# wget https://github.com/microsoft/onnxruntime/releases/download/v1.16.3/onnxruntime-linux-x64-1.16.3.tgz
# tar xzf onnxruntime-linux-x64-1.16.3.tgz
# sudo cp -r onnxruntime-linux-x64-1.16.3/include/* /usr/include/
# sudo cp -r onnxruntime-linux-x64-1.16.3/lib/* /usr/lib/

cmake -S cpp -B build -DCMAKE_BUILD_TYPE=Release -DYOLO_WITH_QT=ON -DYOLO_WITH_ONNXRUNTIME=ON
cmake --build build -j
```

### CUDA / TensorRT (optional)

- Install CUDA 12.x from NVIDIA.
- Install TensorRT.
- For Python: `pip install onnxruntime-gpu` will use CUDA if available.
- For C++: set `-DYOLO_WITH_TENSORRT=ON` and ensure `NvInfer.h` in include path.

## Windows

### Python

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r python\requirements.txt
pip install PySide6 onnxruntime
python scripts\verify_installation.py
```

### C++

- Install Visual Studio 2022 with C++.
- Install vcpkg: `git clone https://github.com/microsoft/vcpkg; .\vcpkg\bootstrap-vcpkg.bat`
- `vcpkg install opencv4 onnxruntime spdlog yaml-cpp nlohmann-json cli11 qtbase --triplet x64-windows`
- `cmake -S cpp -B build -DCMAKE_TOOLCHAIN_FILE=C:\vcpkg\scripts\buildsystems\vcpkg.cmake -DYOLO_WITH_QT=ON`

### Models

```bash
python models/download_models.py --yolo yolov8n,yolo11n
# or manually place ONNX files in models/
```

## Docker (CPU)

```bash
docker build -f docker/Dockerfile.cpu -t offline-yolo:cpu .
docker run -it --rm -v $(pwd)/models:/app/models offline-yolo:cpu python -m yolo_monitor --source 0 --model models/yolov8n.onnx --show
```

## Docker (CUDA)

```bash
docker build -f docker/Dockerfile.cuda -t offline-yolo:cuda .
docker run -it --rm --gpus all -v $(pwd)/models:/app/models offline-yolo:cuda python -m yolo_monitor --source 0 --model models/yolov8n.onnx --device cuda --show
```
