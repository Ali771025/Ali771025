# Troubleshooting

## RTSP lag / reconnect

- Use TCP transport: OpenCV may default to UDP. Set env `OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp`
- Lower buffer: not directly supported in OpenCV, but pipeline has bounded queue and frame dropping
- Check `pipeline.reconnect.enabled` true, backoff 1.5, max_retries 100
- For high-latency network, increase `timeout_ms` to 10000
- Mask password in logs checked via `mask_url`

## Camera not found

- USB: `ls /dev/video*` on Linux, try index 0,1,2
- V4L2 permissions: `sudo usermod -a -G video $USER` then relogin
- Windows: try `dshow://0` or `0` or CAP_DSHOW - OpenCV fallback tries default
- GStreamer: test with `gst-launch-1.0 v4l2src ! videoconvert ! autovideosink`

## Codec issues

- Install GStreamer plugins: `sudo apt install gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly libgstreamer1.0-dev`
- Rebuild OpenCV with GStreamer support if needed
- Try different backend via `source_type` e.g. gstreamer pipeline: `"v4l2src device=/dev/video0 ! videoconvert ! appsink"`

## CUDA mismatch

- Python: `onnxruntime` vs `onnxruntime-gpu` - only one should be installed. Use GPU version for CUDA.
- Check `onnxruntime.get_available_providers()` includes `CUDAExecutionProvider`
- PyTorch vs ONNX Runtime CUDA version mismatch: ensure CUDA 12.x for both
- C++: OpenCV CUDA needs OpenCV built with CUDA. If not, fallback to CPU is automatic.

## Low FPS

Common causes:
- Model too large: use yolov8n/yolo11n, not m/l
- Image size too large: reduce imgsz 640->416
- CPU only: expect 5-15 FPS on modern CPU for 720p with n model. GPU recommended for 30+ FPS
- Frame skipping: `--frame-skip 1` processes every 2nd frame
- Tracking overhead: disable tracking `--tracking disabled` if not needed
- Logging blocking: async writer used, but disk slow may cause queue full - drop policy oldest helps

## ONNX Runtime / TensorRT issues

- `Failed to load ONNX model`: check file exists and is valid ONNX. Try OpenCV DNN fallback `--backend opencv`
- TensorRT engine build fails: ensure TensorRT version matches CUDA, and ONNX opset 12
- `TensorrtExecutionProvider` not available: fallback to CUDA or CPU automatic
- FP16 not supported on older GPUs - disable `--half`

## Qt / PySide6 GUI not showing

- Linux: need X11 or Wayland. On headless server, use `--no-show` and `--save-video`
- Install `libxcb-cursor0`: `sudo apt install libxcb-cursor0`
- Docker: need to forward X11 `-e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix` or use `--no-show`
- PySide6 missing: `pip install PySide6`

## Secrets not masked

- Code uses `mask_url` everywhere logs call `mask_url`
- Ensure you pass `rtsp://user:pass@ip` not via separate file that logs raw? env var masking expands but logs masked
- Check custom scripts that might print source - use `mask_url(source)` helper

## C++ build fails

- `OpenCV not found`: `sudo apt install libopencv-dev`
- `spdlog not found`: `sudo apt install libspdlog-dev libfmt-dev`
- `yaml-cpp not found`: `sudo apt install libyaml-cpp-dev`
- `CLI11 not found`: FetchContent will auto download if not found
- `nlohmann_json not found`: will fetch
- Qt6 not found: install `qt6-base-dev` or disable `-DYOLO_WITH_QT=OFF`
- ONNX Runtime not found: warning, will use OpenCV DNN fallback unless `-DYOLO_WITH_ONNXRUNTIME=OFF`

## Annotation issues

- Image not loading: check path, extension, cv2.imread supported
- Auto-label empty: lower confidence threshold `--conf 0.2`
- YOLO export empty: ensure objects visible checkbox true
- COCO import fails: ensure JSON has images, annotations, categories
- Video frame extraction 0: check codec, try different video or install ffmpeg

## Model not found offline

- Run `python models/download_models.py --yolo yolov8n` once online, then use `--offline`
- Place ONNX manually in `models/` folder
- Check config model path is relative to repo root or absolute

## Still failing?

- Run `python scripts/verify_installation.py` for Python deps
- Run `python -m yolo_monitor --verbose` for debug logs
- C++: set env `SPDLOG_LEVEL=debug` and run with verbose? Check spdlog output
- Open issue with logs - ensure secrets masked before sharing
```
