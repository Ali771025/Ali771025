from __future__ import annotations
import time
from typing import List
import numpy as np
from .base import BaseDetector, Detection, FrameResult
from ..utils.geometry import xyxy_to_xywh, xyxy_to_cxcywh_norm

COCO_CLASSES = ["person","bicycle","car","motorcycle","airplane","bus","train","truck","boat","traffic light","fire hydrant","stop sign","parking meter","bench","bird","cat","dog","horse","sheep","cow","elephant","bear","zebra","giraffe","backpack","umbrella","handbag","tie","suitcase","frisbee","skis","snowboard","sports ball","kite","baseball bat","baseball glove","skateboard","surfboard","tennis racket","bottle","wine glass","cup","fork","knife","spoon","bowl","banana","apple","sandwich","orange","broccoli","carrot","hot dog","pizza","donut","cake","chair","couch","potted plant","bed","dining table","toilet","tv","laptop","mouse","remote","keyboard","cell phone","microwave","oven","toaster","sink","refrigerator","book","clock","vase","scissors","teddy bear","hair drier","toothbrush"]

class UltralyticsDetector(BaseDetector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.model = None

    def load(self):
        try:
            from ultralytics import YOLO
        except ImportError:
            raise ImportError("ultralytics not installed. pip install ultralytics")
        self.model = YOLO(self.model_path)
        # set device
        # class names
        try:
            self.class_names = list(self.model.names.values()) if isinstance(self.model.names, dict) else self.model.names
        except Exception:
            self.class_names = COCO_CLASSES
        self.model_name = self.model_path

    def warmup(self, iters: int = 10):
        if self.model is None:
            self.load()
        dummy = np.zeros((self.imgsz,self.imgsz,3),dtype=np.uint8)
        for _ in range(iters):
            self.detect(dummy)

    def detect(self, frame: np.ndarray, frame_id: int = 0) -> FrameResult:
        if self.model is None:
            self.load()
        t0 = time.time()
        results = self.model.predict(source=frame, imgsz=self.imgsz, conf=self.conf_thres, iou=self.iou_thres, max_det=self.max_det, classes=self.classes if self.classes else None, device=self.device if self.device!="auto" else None, verbose=False)
        inf_time = results[0].speed if hasattr(results[0],'speed') else {}
        inf_ms = float(inf_time.get('inference',0)) if isinstance(inf_time, dict) else 0.0
        h,w = frame.shape[:2]
        detections: List[Detection] = []
        if len(results)>0 and results[0].boxes is not None:
            boxes = results[0].boxes
            xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy,'cpu') else np.array(boxes.xyxy)
            conf = boxes.conf.cpu().numpy() if hasattr(boxes.conf,'cpu') else np.array(boxes.conf)
            cls = boxes.cls.cpu().numpy().astype(int) if hasattr(boxes.cls,'cpu') else np.array(boxes.cls).astype(int)
            for i in range(len(xyxy)):
                x1,y1,x2,y2 = xyxy[i]
                c = float(conf[i])
                cid = int(cls[i])
                cname = self.class_names[cid] if cid < len(self.class_names) else str(cid)
                xyxy_t = (float(x1),float(y1),float(x2),float(y2))
                xywh_t = xyxy_to_xywh(*xyxy_t)
                norm_t = xyxy_to_cxcywh_norm(*xyxy_t, w, h)
                det = Detection(
                    class_id=cid,
                    class_name=cname,
                    confidence=c,
                    xyxy=xyxy_t,
                    xywh=xywh_t,
                    xywh_norm=norm_t,
                    center=((x1+x2)/2,(y1+y2)/2),
                    area=(x2-x1)*(y2-y1),
                    aspect_ratio=(x2-x1)/max(1,y2-y1),
                    track_id=-1,
                    frame_id=frame_id,
                    model_name=self.model_name,
                    inference_time_ms=inf_ms
                )
                detections.append(det)
        return FrameResult(frame_id=frame_id, width=w, height=h, detections=detections, inference_time_ms=inf_ms, timestamp_unix=time.time())
