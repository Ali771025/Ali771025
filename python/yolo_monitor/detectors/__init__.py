from .base import BaseDetector, Detection, FrameResult
from .onnx_detector import OnnxYoloDetector
from .ultralytics_detector import UltralyticsDetector
from .tensorrt_detector import TensorrtYoloDetector

def create_detector(model_path: str, backend: str = "auto", **kwargs) -> BaseDetector:
    backend = backend.lower()
    path_lower = model_path.lower()
    if backend == "auto":
        if path_lower.endswith(".pt"):
            backend = "ultralytics"
        elif path_lower.endswith(".engine") or path_lower.endswith(".trt"):
            backend = "tensorrt"
        else:
            backend = "onnx"
    if backend == "onnx":
        return OnnxYoloDetector(model_path=model_path, **kwargs)
    elif backend == "ultralytics":
        return UltralyticsDetector(model_path=model_path, **kwargs)
    elif backend == "tensorrt":
        return TensorrtYoloDetector(model_path=model_path, **kwargs)
    else:
        raise ValueError(f"Unknown backend: {backend}")

__all__ = ["BaseDetector","Detection","FrameResult","OnnxYoloDetector","UltralyticsDetector","TensorrtYoloDetector","create_detector"]
