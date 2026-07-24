#!/usr/bin/env python3
"""
Verify installation of Python dependencies and optional GPU support
"""
import sys
print("=== Python Verification ===")
print(f"Python: {sys.version}")

checks = [
    ("numpy", "numpy"),
    ("opencv-python", "cv2"),
    ("onnxruntime", "onnxruntime"),
    ("yaml", "yaml"),
    ("pydantic", "pydantic"),
    ("typer", "typer"),
    ("loguru", "loguru"),
]

for pkg, mod in checks:
    try:
        __import__(mod)
        print(f"[OK] {pkg}")
    except ImportError as e:
        print(f"[FAIL] {pkg}: {e}")

# optional
optional = [
    ("ultralytics", "ultralytics"),
    ("torch", "torch"),
    ("onnxruntime-gpu", "onnxruntime"),
    ("PySide6", "PySide6"),
]

print("\n=== Optional ===")
for pkg, mod in optional:
    try:
        m = __import__(mod)
        print(f"[OK] {pkg}")
        if pkg=="torch":
            import torch
            print(f"  CUDA available: {torch.cuda.is_available()}")
            if torch.cuda.is_available():
                print(f"  CUDA devices: {torch.cuda.device_count()} - {torch.cuda.get_device_name(0)}")
    except ImportError as e:
        print(f"[SKIP] {pkg}: {e}")

# ONNX Runtime providers
try:
    import onnxruntime as ort
    print(f"\nONNX Runtime providers: {ort.get_available_providers()}")
except Exception as e:
    print(f"\nONNX Runtime provider check failed: {e}")

# OpenCV
try:
    import cv2
    print(f"\nOpenCV {cv2.__version__}")
    print(f"  CUDA enabled: {cv2.cuda.getCudaEnabledDeviceCount() if hasattr(cv2.cuda,'getCudaEnabledDeviceCount') else 'unknown'}")
except Exception as e:
    print(f"OpenCV check failed: {e}")

print("\nVerification complete")
