from __future__ import annotations
import time
from pathlib import Path
from typing import List
import numpy as np
import cv2
from .base import BaseDetector, Detection, FrameResult, nms_boxes
from ..utils.geometry import xyxy_to_xywh, xyxy_to_cxcywh_norm

# TensorRT detector - optional, requires tensorrt and pycuda or torch tensorrt
# This is a stub that falls back to ONNX if TensorRT engine not loadable via ONNX Runtime tensorrt provider

class TensorrtYoloDetector(BaseDetector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.session = None
        self.input_name = None
        self.output_names = None
        self.class_names = ["person","bicycle","car","motorcycle","airplane","bus","train","truck","boat","traffic light","fire hydrant","stop sign","parking meter","bench","bird","cat","dog","horse","sheep","cow","elephant","bear","zebra","giraffe","backpack","umbrella","handbag","tie","suitcase","frisbee","skis","snowboard","sports ball","kite","baseball bat","baseball glove","skateboard","surfboard","tennis racket","bottle","wine glass","cup","fork","knife","spoon","bowl","banana","apple","sandwich","orange","broccoli","carrot","hot dog","pizza","donut","cake","chair","couch","potted plant","bed","dining table","toilet","tv","laptop","mouse","remote","keyboard","cell phone","microwave","oven","toaster","sink","refrigerator","book","clock","vase","scissors","teddy bear","hair drier","toothbrush"]

    def load(self):
        try:
            import onnxruntime as ort
        except ImportError:
            raise ImportError("onnxruntime required for TensorRT fallback")
        # If model path is .engine/.trt, attempt to use TensorRT execution provider via onnx? Actually TensorRT engine files aren't ONNX.
        # For simplicity, if model ends with .engine or .trt, we require it to be ONNX renamed or we raise.
        p = Path(self.model_path)
        if p.suffix in [".engine",".trt"]:
            # Attempt to load via TensorRT direct would need tensorrt lib; for offline generic, use trt
            # We implement a minimal TensorRT loader if tensorrt available
            try:
                import tensorrt as trt
                # TODO: implement full TRT engine loader with bindings
                # For now fallback message
                raise RuntimeError("Direct .engine loading requires custom TensorRT bindings - use .onnx with TensorRT provider as intermediate")
            except ImportError:
                raise ImportError("tensorrt library not installed, cannot load .engine directly. Export ONNX and use provider TensorrtExecutionProvider")
        # Otherwise treat as ONNX with TensorRT provider
        so = ort.SessionOptions()
        providers = ["TensorrtExecutionProvider","CUDAExecutionProvider","CPUExecutionProvider"]
        try:
            self.session = ort.InferenceSession(str(p), sess_options=so, providers=providers)
        except Exception as e:
            # fallback to cpu
            self.session = ort.InferenceSession(str(p), sess_options=so, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]

    def warmup(self, iters: int = 10):
        if self.session is None:
            self.load()
        dummy = np.zeros((self.imgsz,self.imgsz,3),dtype=np.uint8)
        for _ in range(iters):
            self.detect(dummy)

    def _preprocess(self, frame: np.ndarray):
        h,w = frame.shape[:2]
        r = min(self.imgsz/h, self.imgsz/w)
        new_unpad = (int(round(w*r)), int(round(h*r)))
        dw,dh = self.imgsz - new_unpad[0], self.imgsz - new_unpad[1]
        dw/=2; dh/=2
        resized = cv2.resize(frame, new_unpad, interpolation=cv2.INTER_LINEAR)
        top,bottom = int(round(dh-0.1)), int(round(dh+0.1))
        left,right = int(round(dw-0.1)), int(round(dw+0.1))
        out = cv2.copyMakeBorder(resized, top,bottom,left,right, cv2.BORDER_CONSTANT, value=(114,114,114))
        out_rgb = cv2.cvtColor(out, cv2.COLOR_BGR2RGB)
        out_rgb = out_rgb.astype(np.float32)/255.0
        out_chw = np.transpose(out_rgb, (2,0,1))
        out_batch = np.expand_dims(out_chw, axis=0)
        if self.half:
            out_batch = out_batch.astype(np.float16)
        return out_batch, r, (dw,dh), (h,w)

    def detect(self, frame: np.ndarray, frame_id: int = 0) -> FrameResult:
        if self.session is None:
            self.load()
        t0 = time.time()
        inp,ratio,dwdh,orig_shape = self._preprocess(frame)
        outputs = self.session.run(self.output_names, {self.input_name: inp})
        inf_ms = (time.time()-t0)*1000
        # Reuse postprocess from ONNX detector
        from .onnx_detector import OnnxYoloDetector
        # create temp detector for postprocess
        tmp = OnnxYoloDetector(model_path=self.model_path, device=self.device, imgsz=self.imgsz, conf_thres=self.conf_thres, iou_thres=self.iou_thres, max_det=self.max_det, classes=self.classes, half=self.half)
        tmp.class_names = self.class_names
        tmp.model_name = self.model_path
        dets = tmp._postprocess(outputs, ratio, dwdh, orig_shape, frame_id, inf_ms)
        h,w = frame.shape[:2]
        return FrameResult(frame_id=frame_id, width=w, height=h, detections=dets, inference_time_ms=inf_ms, timestamp_unix=time.time())
