# offline-yolo-monitor-annotator — Professional Offline YOLO + Monitoring + AI Annotator + Tiny LLM

**۱۰۰٪ آفلاین، بدون اینترنت در زمان اجرا، بدون کلود، بدون تله‌متری. پشتیبانی کامل GPU + CPU. دو پیاده‌سازی Python و C++ + Annotator حرفه‌ای Batch + LLM فارسی.**

---

## 📦 پروژه‌ها داخل این ریپو

این ریپو **سه پروژه کامل** است:

### 1. Python Detection / Monitoring (`python/yolo_monitor/`)
- ورودی: USB (`0` / `dshow://0`), V4L2 `/dev/video0`, RTSP `rtsp://user:pass@ip/stream`, HTTP/MJPEG `http://ip/video`, RTMP, GStreamer pipeline, Video file mp4/avi/mkv, پوشه عکس jpg/png
- Detector: ONNX Runtime (CPU/CUDA), Ultralytics `.pt` اختیاری, TensorRT `.engine` اختیاری
- پایپلاین تردی: capture → inference → tracking (IoU) → logging → render با BoundedQueue drop-oldest و reconnect exponential backoff
- مانیتورینگ: OpenCV HighGUI + Qt6 optional، FPS, inference FPS, latency, source/status, resolution, model, device, conf/iou, count + کلیدهای `q/p/s/r/l/+/[/]`
- لاگ کامل: CSV/JSONL/both/SQLite با `mask_url()` مخفی کردن پسورد RTSP + تمام مختصات `xyxy, xywh, normalized cxcywh, center, area, aspect, track_id, inference_ms, latency_ms`

### 2. C++ Detection / Monitoring (`cpp/`)
- C++20, CMake 3.24+, OpenCV 4.x, ONNX Runtime optional, TensorRT optional, spdlog, yaml-cpp, nlohmann_json, CLI11, Qt6 optional, GTest
- کتابخانه `yolo_core`, `yolo_detector`, `yolo_source`, `yolo_pipeline`, `yolo_app`, `yolo_gui`, `yolo_annotator_core`
- `OpenCVDNNDetector` همیشه build می‌شود (fallback)، `OnnxDetector` با CUDAExecutionProvider، preallocated buffers، zero-copy
- لاگ async با secret masking

### 3. Annotator ها
- **قدیمی**: `python/yolo_annotator/` + `cpp/src/annotator_*` — YOLO/COCO/VOC export/import، auto-label YOLO local، SAM GrabCut fallback
- **جدید حرفه‌ای Pro-Annotator 2.0**: `pro-annotator/` — کاملاً جدید از صفر:
  - Batch هزاران عکس فقط کلاس‌های دلخواه شما `--wanted-classes person,car`
  - Tiny LLM آفلاین GGUF/Transformers/ONNX/Dummy برای QA لیبل، تحلیل دیتاست، پرسش طبیعی فارسی `عکس‌هایی که بیش از 3 ماشین دارند`
  - Dataset Manager: stats, split train/val/test, active learning, duplicate finder
  - UI دارک حرفه‌ای: thumbnail search, canvas zoom/pan, object list, class manager checkbox filter, batch panel, LLM panel

---

## 📁 ساختار ریپو

```
.
├── README.md (همین فایل - راهنمای کامل)
├── LICENSE
├── configs/ default.yaml, usb_camera.yaml, rtsp_camera.yaml, ip_http_camera.yaml, video_file.yaml, annotator.yaml
├── models/ .gitkeep + download_models.py, export_onnx.py, export_tensorrt.py (مدل‌ها اینجا کش)
├── python/
│   ├── pyproject.toml, requirements.txt
│   ├── yolo_monitor/ cli.py, config.py, sources/, detectors/, pipeline/, tracking/, ui/, utils/, logging/
│   └── yolo_annotator/ cli.py, core/, ai/, exporters/, importers/, ui/
├── cpp/
│   ├── CMakeLists.txt, vcpkg.json, conanfile.txt
│   ├── include/yolo/ core/, detector/, source/, pipeline/, logging/, gui/, annotator_core/
│   ├── src/ core/, detector/, source/, pipeline/, logging/, app/main.cpp, gui/, annotator_*
│   └── tests/
├── pro-annotator/  # پروژه جدید حرفه‌ای کامل
│   ├── README.md
│   ├── requirements.txt, pyproject.toml, run.sh
│   ├── configs/annotator.yaml
│   ├── models/ .gitkeep
│   ├── pro_annotator/ core/, ai/ detector, sam, llm_analyzer, batch_processor, exporters/, importers/, ui/ main_window, canvas, panels, styles, utils/
│   ├── scripts/download_models.py, download_llm.py
│   ├── tests/test_annotation.py
│   └── docs/ LLM_GUIDE.md, BATCH_GUIDE.md
├── scripts/ benchmark.py, verify_installation.py, run_python_usb.sh, run_python_rtsp.sh, run_cpp_*.sh
├── docker/ Dockerfile.cpu, Dockerfile.cuda, docker-compose.yml
├── docs/ installation.md, python_usage.md, cpp_usage.md, annotation_guide.md, model_export.md, troubleshooting.md
└── datasets/ .gitkeep
```

---

## 🚀 نصب سریع (Ubuntu 22.04+, Windows 10/11, Python 3.10+)

### Ubuntu 22.04 - پیش‌نیاز

```bash
sudo apt update
sudo apt install -y build-essential cmake ninja-build pkg-config git wget curl \
  libopencv-dev libspdlog-dev libyaml-cpp-dev nlohmann-json3-dev libcli11-dev \
  qt6-base-dev libgtest-dev libxcb-cursor0 \
  python3.10-venv python3-pip python3-dev \
  gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-libav
```

### GPU NVIDIA (اختیاری برای 30+ FPS)

```bash
nvidia-smi  # باید درایور نصب باشد
# CUDA 12.x از https://developer.nvidia.com/cuda-toolkit
nvcc --version
# cuDNN + TensorRT از NVIDIA (برای TensorRT backend اختیاری)
```

### Python venv + نصب

```bash
git clone https://github.com/Ali771025/Ali771025.git
cd Ali771025
git checkout arena/019f92fc-ali771025

python3 -m venv .venv
source .venv/bin/activate
pip install -U pip

# پروژه اصلی
pip install -r python/requirements.txt
pip install -e python/
pip install PySide6  # GUI اختیاری

# پروژه جدید حرفه‌ای
pip install -r pro-annotator/requirements.txt
pip install -e pro-annotator/
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu  # برای GGUF LLM

# تست نصب
python scripts/verify_installation.py
```

### Windows

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r python\requirements.txt
pip install PySide6
# vcpkg برای C++
git clone https://github.com/microsoft/vcpkg
.\vcpkg\bootstrap-vcpkg.bat
vcpkg install opencv4 onnxruntime spdlog yaml-cpp nlohmann-json cli11 qtbase --triplet x64-windows
cmake -S cpp -B build -DCMAKE_TOOLCHAIN_FILE=C:\vcpkg\scripts\buildsystems\vcpkg.cmake -DYOLO_WITH_QT=ON -DYOLO_WITH_ONNXRUNTIME=ON
cmake --build build --config Release
```

---

## 📥 دانلود مدل‌ها - یکبار آنلاین، بعد کاملاً آفلاین

```bash
# YOLO (6MB تا 40MB)
python models/download_models.py --yolo yolov8n,yolo11n --dest models
python pro-annotator/scripts/download_models.py --yolo yolov8n --dest pro-annotator/models
ls models/*.onnx
# yolov8n.onnx, yolo11n.onnx

# LLM کوچک آفلاین برای Annotator حرفه‌ای (0.4GB تا 2.2GB) - فارسی عالی Qwen2
python pro-annotator/scripts/download_llm.py --list
python pro-annotator/scripts/download_llm.py --model qwen2-0.5b --dest pro-annotator/models/llm
# گزینه‌ها:
# qwen2-0.5b Q4 0.4GB سریعترین، فارسی+انگلیسی عالی - توصیه
# qwen2-1.5b Q4 1.0GB بهتر
# tinyllama 1.1B Q4 0.6GB انگلیسی
# phi-2 2.7B Q4 1.6GB
# phi-3-mini 3.8B Q4 2.2GB

ls pro-annotator/models/llm/
# qwen2-0_5b-instruct-q4_0.gguf

# حالا با --offline هیچ اینترنت لازم نیست
```

---

## ▶️ اجرای Python Detection / Monitoring

### USB وبکم (لینوکس V4L2 / ویندوز DirectShow)

```bash
python -m yolo_monitor --source 0 --model models/yolov8n.onnx --device cpu --show --log detections.jsonl
python -m yolo_monitor --source /dev/video0 --model models/yolov8n.onnx --device auto --conf 0.35 --iou 0.45 --show
# کلیدها: q/Esc خروج, p توقف, s اسنپ‌شات snapshots/snap_*.jpg, r رکورد, l label, f FPS, +/- conf, [/] iou
```

### RTSP دوربین مداربسته - با reconnect خودکار + مخفی پسورد

```bash
export CAMERA_USER=admin
export CAMERA_PASSWORD=12345
python -m yolo_monitor --source rtsp://CAMERA_USER:CAMERA_PASSWORD@192.168.1.10:554/stream --model models/yolov8n.onnx --device cuda --show --log rtsp.jsonl

# یا مستقیم (پسورد در لاگ ماسک می‌شود ****)
python -m yolo_monitor --source rtsp://admin:12345@192.168.1.10:554/stream --model models/yolov8s.onnx --backend onnx --device cuda --show

# کاهش lag RTSP TCP
OPENCV_FFMPEG_CAPTURE_OPTIONS="rtsp_transport;tcp" python -m yolo_monitor --source rtsp://...
```

### IP HTTP / MJPEG

```bash
python -m yolo_monitor --source http://192.168.1.11/video --model models/yolov8n.onnx --show
python -m yolo_monitor --source http://192.168.1.11/mjpeg --model models/yolov8n.onnx --config configs/ip_http_camera.yaml
```

### ویدئو فایل + ذخیره خروجی

```bash
python -m yolo_monitor --source video.mp4 --model models/yolov8n.onnx --conf 0.35 --iou 0.45 --save-video out.mp4 --log out.jsonl --log-format both
# both = csv + jsonl
# لاگ شامل: timestamp_unix/iso, source_id ماسک, xyxy, xywh, normalized cxcywh, center, area, aspect, track_id, inference_ms, latency_ms
```

### پوشه عکس Batch

```bash
python -m yolo_monitor --source datasets/images --source-type images --model models/yolov8n.onnx --show --log batch.jsonl
```

### GStreamer پیشرفته

```bash
python -m yolo_monitor --source "v4l2src device=/dev/video0 ! videoconvert ! appsink" --source-type gstreamer --model models/yolov8n.onnx --show
```

### با YAML

```bash
python -m yolo_monitor --config configs/default.yaml
python -m yolo_monitor --config configs/usb_camera.yaml --source 0 --offline
```

### GPU - Python

```bash
# نصب GPU runtime (به جای cpu)
pip uninstall onnxruntime -y
pip install onnxruntime-gpu==1.16.3
pip install ultralytics torch torchvision --index-url https://download.pytorch.org/whl/cu121

python -c "import onnxruntime as ort; print(ort.get_available_providers())"
# باید CUDAExecutionProvider داشته باشد

python -m yolo_monitor --source 0 --model models/yolov8n.onnx --device cuda --half --show --log out.jsonl
python -m yolo_monitor --source video.mp4 --model models/yolov8n.onnx --device cuda:0 --conf 0.4

# بنچمارک FPS, p50/p95/p99 latency
python scripts/benchmark.py --model models/yolov8n.onnx --device cpu --iters 100
python scripts/benchmark.py --model models/yolov8n.onnx --device cuda --iters 100 --source video.mp4
# هدف: 1080p USB YOLOv8n GPU >=30 FPS, CPU 720p >=10 FPS

# بهینه‌سازی
# مدل کوچک yolo11n, imgsz 416, frame_skip 1, tracking خاموش
python -m yolo_monitor --source 0 --model models/yolo11n.onnx --device cuda --imgsz 416 --frame-skip 1 --show
```

---

## ▶️ اجرای C++ Detection / Monitoring

### Build CPU

```bash
cmake -S cpp -B build -DCMAKE_BUILD_TYPE=Release -DYOLO_WITH_QT=ON -DYOLO_WITH_ONNXRUNTIME=ON -DYOLO_BUILD_TESTS=ON
cmake --build build -j$(nproc)
./build/yolo_tests

./build/yolo_app --source 0 --model models/yolov8n.onnx --device cpu --show --log out.csv --conf 0.35 --iou 0.45
./build/yolo_app --source video.mp4 --model models/yolov8n.onnx --save-video out.mp4 --log out.jsonl --log-format both
./build/yolo_app --source datasets/images --model models/yolov8n.onnx --log batch.csv --config configs/default.yaml
./build/yolo_gui --source 0 --model models/yolov8n.onnx --device cpu  # Qt GUI
```

### Build GPU - CUDA + TensorRT

```bash
# ONNX Runtime GPU پیش‌ساخته
wget https://github.com/microsoft/onnxruntime/releases/download/v1.16.3/onnxruntime-linux-x64-gpu-1.16.3.tgz
tar xzf onnxruntime-linux-x64-gpu-1.16.3.tgz -C /opt
export ONNXRUNTIME_ROOT=/opt/onnxruntime-linux-x64-gpu-1.16.3

# Build
cmake -S cpp -B build -DCMAKE_BUILD_TYPE=Release \
  -DYOLO_WITH_QT=ON \
  -DYOLO_WITH_ONNXRUNTIME=ON -DONNXRUNTIME_ROOT=$ONNXRUNTIME_ROOT \
  -DYOLO_WITH_TENSORRT=ON \
  -DYOLO_WITH_CUDA=ON

cmake --build build -j

# Export TensorRT engine
python models/export_tensorrt.py --model models/yolov8n.onnx --imgsz 640 --half
# حالا .engine

./build/yolo_app --source 0 --model models/yolov8n.engine --backend tensorrt --device tensorrt --show
./build/yolo_app --source 0 --model models/yolov8n.onnx --backend onnx --device cuda --half --show
```

**نکات C++ GPU:**
- `OpenCVDNNDetector` اگر `device=cuda` و OpenCV با CUDA باشد → `DNN_BACKEND_CUDA` + `DNN_TARGET_CUDA_FP16` وگرنه fallback CPU خودکار
- `OnnxDetector` CUDAExecutionProvider اگر موجود باشد GPU وگرنه CPU
- Preallocated buffers، zero-copy، async logging

### C++ Annotator

```bash
./build/yolo_annotator --project datasets/my_dataset --model models/yolov8n.onnx
./build/yolo_annotator --project datasets/my_dataset --model models/yolov8n.onnx --images data/images --export-format yolo --export-path export/ --headless
```

---

## ▶️ اجرای Python Annotator قدیمی

```bash
python -m yolo_annotator --project datasets/my_dataset --model models/yolov8n.onnx --offline
python -m yolo_annotator --project datasets/my_dataset --model models/yolov8n.onnx --headless --images data/raw --export-format yolo --export-path datasets/my_dataset/export_yolo
```

---

## ▶️ اجرای Pro-Annotator 2.0 حرفه‌ای جدید (Batch + Wanted Classes + Tiny LLM)

### GUI حرفه‌ای

```bash
cd pro-annotator
pip install PySide6
# heuristic LLM بدون مدل (همیشه کار)
python -m pro_annotator --project datasets/my_dataset --model ../models/yolov8n.onnx --offline

# با LLM کوچک GGUF فارسی - بهترین تجربه
python -m pro_annotator --project datasets/my_dataset \
  --model ../models/yolov8n.onnx \
  --llm-model models/llm/qwen2-0_5b-instruct-q4_0.gguf --llm-backend llama_cpp --offline

# نصب llama-cpp برای GGUF
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
```

**داخل UI:**
- تب Images: thumbnail با سرچ + QA ⚠️ اگر score پایین
- تب Classes: چک‌باکس Wanted Classes → فقط `person,car` تیک بزن → بقیه نادیده
- تب Batch: Browse پوشه 10 هزار عکس → Conf 0.35 → Start Batch (فقط wanted, progress bar, autosave هر ۵۰ عکس، UI فریز نمی‌شود)
- تب LLM QA: Load LLM → Analyze Current Image (تکراری، tiny، out_of_bounds) → Analyze Dataset (توزیع، imbalance) → Query: بنویس `images with more than 3 cars` یا فارسی `عکس‌هایی که ماشین ندارند`
- Canvas: drag ساخت bbox، move، zoom wheel، Ctrl+drag pan، Del حذف
- Object List: 👁 ویزیبل 🤖 AI
- Stats: Images, Objects, Reviewed, Class distribution

### Batch فقط کلاس‌های دلخواه از CLI

```bash
python -m pro_annotator --project datasets/my_dataset \
  --model models/yolov8n.onnx \
  --batch-folder /data/10000_images --wanted-classes person,car --conf 0.4 --recursive --offline
```

### Headless Batch + LLM QA + Export برای تولید/سرور

```bash
python -m pro_annotator --project datasets/tehran_traffic \
  --model models/yolo11n.onnx \
  --batch-folder /data/tehran_street --wanted-classes person,car \
  --llm-model models/llm/qwen2-0_5b-instruct-q4_0.gguf --llm-backend llama_cpp \
  --headless --export-format yolo --export-path datasets/tehran_traffic/export --offline

# خروجی:
# datasets/tehran_traffic/export_yolo/labels/*.txt (فقط person,car)
# datasets/tehran_traffic/export_yolo/dataset.yaml
# datasets/tehran_traffic/llm_report.json (تحلیل LLM)
# datasets/tehran_traffic/dataset_stats.json
```

**LLM چه کار می‌کند؟** `docs/LLM_GUIDE.md`
- تحلیل هر عکس: باکس تکراری IoU>0.95، کوچک <8px، خارج کادر، low conf
- توضیح خودکار: "این عکس 3 ماشین و 1 عابر دارد..."
- مدیریت دیتاست: توزیع کلاس، imbalance، پیشنهاد merge car+truck→vehicle، rename
- پرسش طبیعی: فارسی و انگلیسی

---

## 🐳 Docker - بالا آوردن

**CPU:**
```bash
docker build -f docker/Dockerfile.cpu -t offline-yolo:cpu .
docker run -it --rm -v $(pwd)/models:/app/models -v $(pwd)/datasets:/app/datasets offline-yolo:cpu python -m yolo_monitor --source 0 --model models/yolov8n.onnx --no-show --log /tmp/out.jsonl

# با X11 لینوکس برای نمایش:
xhost +local:docker
docker run -it --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix -v $(pwd)/models:/app/models offline-yolo:cpu
```

**CUDA:**
```bash
docker build -f docker/Dockerfile.cuda -t offline-yolo:cuda .
docker run -it --rm --gpus all -v $(pwd)/models:/app/models offline-yolo:cuda python -m yolo_monitor --source 0 --model models/yolov8n.onnx --device cuda --show
docker-compose -f docker/docker-compose.yml up yolo-cuda
```

---

## 🚀 بالا آوردن به عنوان سرویس 24/7 (Production)

**systemd برای RTSP:**

`/etc/systemd/system/yolo-monitor.service`:
```ini
[Unit]
Description=Offline YOLO Monitor
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/user/Ali771025
Environment=CAMERA_USER=admin
Environment=CAMERA_PASSWORD=secret
Environment=OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp
ExecStart=/home/user/Ali771025/.venv/bin/python -m yolo_monitor --source rtsp://CAMERA_USER:CAMERA_PASSWORD@192.168.1.10/stream --model models/yolov8n.onnx --device cuda --no-show --log /var/log/yolo/detections.jsonl --log-format jsonl
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
```bash
sudo mkdir -p /var/log/yolo && sudo chown $USER /var/log/yolo
sudo systemctl enable --now yolo-monitor
sudo journalctl -u yolo-monitor -f
```

**Pro-Annotator batch به عنوان cron job headless.**

---

## 🔧 توسعه با GPU - راهنمای برنامه‌نویس

### Python توسعه GPU

```python
# yolo_monitor/detectors/onnx_detector.py
import onnxruntime as ort
print(ort.get_available_providers()) # ['TensorrtExecutionProvider','CUDAExecutionProvider','CPUExecutionProvider']

# device="cuda" → CUDAExecutionProvider
# device="tensorrt" → TensorrtExecutionProvider + CUDA
# half=True → FP16
```

- بهینه‌سازی: letterbox resize CPU, normalize 0-1, CHW, batch=1, preallocate, async logging
- بنچمارک: `scripts/benchmark.py` avg/p50/p95/p99 latency

### C++ توسعه GPU

```cpp
// detector factory
auto det = yolo::create_detector("models/yolov8n.onnx","onnx","cuda",640,0.35,0.45);
det->load(); // try CUDA provider
auto res = det->detect(frame);

// OpenCV DNN CUDA
net.setPreferableBackend(cv::dnn::DNN_BACKEND_CUDA);
net.setPreferableTarget(cv::dnn::DNN_TARGET_CUDA_FP16);
```

- CMake: `-DYOLO_WITH_ONNXRUNTIME=ON -DONNXRUNTIME_ROOT=/opt/onnxruntime-gpu -DYOLO_WITH_TENSORRT=ON`
- اگر TensorRT engine دارید: `export_onnx.py` → `export_tensorrt.py` → `.engine`

### LLM GPU

- GGUF llama-cpp فعلاً CPU (سریع برای 0.5B)
- برای GPU LLM: `pip install transformers accelerate torch` + `device=cuda` در `LLMAnalyzer` با `transformers` backend

---

## 🧪 تست

```bash
pytest python/tests -v
pytest pro-annotator/tests -v
cd build && ./yolo_tests
```

---

## ❓ عیب‌یابی GPU

- **CUDAExecutionProvider not found**: `pip install onnxruntime-gpu` نه `onnxruntime`
- **OpenCV CUDA NO**: OpenCV apt معمولاً CUDA ندارد، باید از source با `-DWITH_CUDA=ON` بسازی
- **Low FPS**: مدل کوچک yolo11n، imgsz 416، frame_skip 1
- **RTSP lag**: `OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp` + `timeout_ms 10000` + bounded queue
- **Qt نمی‌آید**: `sudo apt install libxcb-cursor0` یا `--no-show`
- **LLM load fail**: `dummy` backend همیشه کار می‌کند، برای GGUF `llama-cpp-python` نصب کن

---

## 📄 لایسنس MIT

تمام پروژه 100% آفلاین، بدون تله‌متری، بدون کلود. مدل‌ها در `./models` کش.
