# Model Export Guide

## Download

One-time online step, then fully offline:

```bash
python models/download_models.py --yolo yolov8n,yolo11n
python models/download_models.py --list
```

Manually: download ONNX from Ultralytics releases and place in `models/`.

## Export .pt -> ONNX

Requires Ultralytics:

```bash
pip install ultralytics
python models/export_onnx.py --model yolov8n.pt --imgsz 640 --opset 12
# output: yolov8n.onnx
mv yolov8n.onnx models/
```

Options:
- `--half`: FP16
- `--dynamic`: dynamic batch (not recommended for TensorRT)
- `--simplify`: onnx-simplifier

## Export ONNX -> TensorRT .engine

Requires TensorRT and optionally PyCUDA or Ultralytics:

```bash
python models/export_tensorrt.py --model models/yolov8n.onnx --imgsz 640 --half
# via Ultralytics:
# python -c "from ultralytics import YOLO; YOLO('yolov8n.pt').export(format='engine', half=True)"
```

C++ can load:
- `.onnx` via ONNX Runtime (CPU/CUDA) or OpenCV DNN
- `.engine` via TensorRT (if compiled with TensorRT) - currently stub falls back to ONNX Runtime TensorRT provider

## Custom YOLO Training

Train with Ultralytics:

```bash
yolo detect train data=datasets/my_dataset/dataset.yaml model=yolov8n.pt epochs=100 imgsz=640
# then export best.pt to ONNX
python models/export_onnx.py --model runs/detect/train/weights/best.pt --imgsz 640
```

Exported model can be used in both Python and C++ monitor and annotator.

## MobileSAM / EdgeSAM ONNX

For AI-assisted segmentation:

- Download MobileSAM checkpoint and convert to ONNX using MobileSAM repo's export script
- Place as `models/mobile_sam.onnx`
- Annotator will use it if present, otherwise GrabCut fallback

Example (if you have MobileSAM):

```bash
# in MobileSAM repo
python -c "import torch; ..." # follow MobileSAM ONNX export guide
# output mobile_sam.onnx -> copy to our models/
```

## Verify ONNX

```python
import onnx
model = onnx.load("models/yolov8n.onnx")
onnx.checker.check_model(model)
print("OK")
```

## Optimizations

- FP16: halve memory, faster on GPU/TensorRT
- INT8: needs calibration, via TensorRT
- Smaller input size 416 or 320 for CPU speed at cost of accuracy
- Use YOLO11n/YOLOv8n for fastest, YOLO11s/m for more accuracy

## Offline Policy

- All export scripts require internet only once for pip and model download
- Runtime loads from local files only when --offline flag set
- No telemetry in Python or C++
```
