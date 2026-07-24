#!/usr/bin/env python3
"""
Export Ultralytics YOLO .pt to ONNX for offline ONNX Runtime inference
"""
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Export YOLO pt to ONNX")
    parser.add_argument("--model", type=str, required=True, help="Path to .pt file")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument("--opset", type=int, default=12, help="ONNX opset")
    parser.add_argument("--half", action="store_true", help="FP16")
    parser.add_argument("--dynamic", action="store_true", help="Dynamic batch")
    parser.add_argument("--simplify", action="store_true", help="Simplify ONNX")
    args = parser.parse_args()

    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics not installed: pip install ultralytics")
        return

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"Model not found: {model_path}")
        return

    model = YOLO(str(model_path))
    print(f"Exporting {model_path} to ONNX, imgsz={args.imgsz}")
    # export
    result = model.export(format="onnx", imgsz=args.imgsz, opset=args.opset, half=args.half, dynamic=args.dynamic, simplify=args.simplify)
    print(f"Exported: {result}")

if __name__ == "__main__":
    main()
