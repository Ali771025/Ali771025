from __future__ import annotations
import time
from pathlib import Path
from typing import List, Optional
import cv2
import numpy as np
from .base import BaseDetector, Detection, FrameResult, nms_boxes
from ..utils.geometry import xyxy_to_xywh, xyxy_to_cxcywh_norm

COCO_CLASSES = ["person","bicycle","car","motorcycle","airplane","bus","train","truck","boat","traffic light","fire hydrant","stop sign","parking meter","bench","bird","cat","dog","horse","sheep","cow","elephant","bear","zebra","giraffe","backpack","umbrella","handbag","tie","suitcase","frisbee","skis","snowboard","sports ball","kite","baseball bat","baseball glove","skateboard","surfboard","tennis racket","bottle","wine glass","cup","fork","knife","spoon","bowl","banana","apple","sandwich","orange","broccoli","carrot","hot dog","pizza","donut","cake","chair","couch","potted plant","bed","dining table","toilet","tv","laptop","mouse","remote","keyboard","cell phone","microwave","oven","toaster","sink","refrigerator","book","clock","vase","scissors","teddy bear","hair drier","toothbrush"]

class OnnxYoloDetector(BaseDetector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.session = None
        self.input_name = None
        self.output_names = None
        self.input_shape = None  # e.g. (1,3,640,640)
        self.is_yolo_v5 = False

    def load(self):
        try:
            import onnxruntime as ort
        except ImportError:
            raise ImportError("onnxruntime not installed. pip install onnxruntime or onnxruntime-gpu")
        model_path = Path(self.model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        providers = []
        dev = self.device.lower()
        if dev in ("cuda","cuda:0","gpu") or dev.startswith("cuda"):
            # try GPU
            providers = ["CUDAExecutionProvider","CPUExecutionProvider"]
        elif dev == "auto":
            # try to use CUDA if available
            try:
                available = ort.get_available_providers()
                if "CUDAExecutionProvider" in available:
                    providers = ["CUDAExecutionProvider","CPUExecutionProvider"]
                else:
                    providers = ["CPUExecutionProvider"]
            except Exception:
                providers = ["CPUExecutionProvider"]
        else:
            providers = ["CPUExecutionProvider"]

        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(str(model_path), sess_options=so, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        self.input_shape = self.session.get_inputs()[0].shape  # e.g. [1,3,640,640] maybe dynamic
        # handle dynamic shape
        if isinstance(self.input_shape, (list,tuple)):
            # replace None with imgsz
            shape = []
            for dim in self.input_shape:
                if isinstance(dim,str) or dim is None:
                    shape.append(self.imgsz)
                else:
                    shape.append(dim)
            self.input_shape = shape
        self.class_names = COCO_CLASSES
        # Try to read class names from accompanying yaml if exists
        yaml_path = model_path.with_suffix(".yaml")
        if yaml_path.exists():
            try:
                import yaml
                data = yaml.safe_load(yaml_path.read_text())
                if "names" in data:
                    self.class_names = list(data["names"].values()) if isinstance(data["names"], dict) else data["names"]
            except Exception:
                pass
        self.model_name = model_path.name

    def warmup(self, iters: int = 10):
        if self.session is None:
            self.load()
        dummy = np.zeros((self.imgsz, self.imgsz, 3), dtype=np.uint8)
        for _ in range(iters):
            self.detect(dummy)

    def _preprocess(self, frame: np.ndarray):
        # letterbox
        h,w = frame.shape[:2]
        r = min(self.imgsz / h, self.imgsz / w)
        new_unpad = (int(round(w*r)), int(round(h*r)))
        dw, dh = self.imgsz - new_unpad[0], self.imgsz - new_unpad[1]
        dw/=2; dh/=2
        resized = cv2.resize(frame, new_unpad, interpolation=cv2.INTER_LINEAR)
        top,bottom = int(round(dh-0.1)), int(round(dh+0.1))
        left,right = int(round(dw-0.1)), int(round(dw+0.1))
        out = cv2.copyMakeBorder(resized, top,bottom,left,right, cv2.BORDER_CONSTANT, value=(114,114,114))
        # BGR to RGB, normalize 0-1, CHW
        out_rgb = cv2.cvtColor(out, cv2.COLOR_BGR2RGB)
        out_rgb = out_rgb.astype(np.float32)/255.0
        out_chw = np.transpose(out_rgb, (2,0,1))
        out_batch = np.expand_dims(out_chw, axis=0)  # 1,3,640,640
        if self.half:
            out_batch = out_batch.astype(np.float16)
        return out_batch, r, (dw,dh), (h,w)

    def _postprocess(self, outputs, ratio, dwdh, orig_shape, frame_id, inference_time):
        # outputs: list of outputs from onnx session
        # YOLOv8 output shape: (1,84,8400) or (1, 84, 8400) - 4 bbox + 80 classes
        # YOLOv5 output shape: (1,25200,85) - x,y,w,h,obj,classes...
        pred = outputs[0]
        # handle multiple outputs if model has more? use first
        orig_h, orig_w = orig_shape
        detections: List[Detection] = []
        if pred.ndim == 3:
            # shape (1,84,8400) -> transpose to (1,8400,84)
            if pred.shape[1] < pred.shape[2]:
                # 84,8400 -> transpose
                pred = np.transpose(pred, (0,2,1))
            # now (1,8400,84)
            pred = pred[0]  # (8400,84)
            # split
            # 0:4 bbox cx,cy,w,h; 4:84 classes
            boxes_cxcywh = pred[:, :4]
            scores = pred[:, 4:]
            # max class score
            max_scores = np.max(scores, axis=1)
            class_ids = np.argmax(scores, axis=1)
            # filter by conf
            mask = max_scores >= self.conf_thres
            if self.classes:
                mask = mask & np.isin(class_ids, self.classes)
            boxes_cxcywh = boxes_cxcywh[mask]
            max_scores = max_scores[mask]
            class_ids = class_ids[mask]
            # convert cxcywh to xyxy in letterbox image coordinates
            xyxy = np.zeros_like(boxes_cxcywh)
            xyxy[:,0] = boxes_cxcywh[:,0] - boxes_cxcywh[:,2]/2
            xyxy[:,1] = boxes_cxcywh[:,1] - boxes_cxcywh[:,3]/2
            xyxy[:,2] = boxes_cxcywh[:,0] + boxes_cxcywh[:,2]/2
            xyxy[:,3] = boxes_cxcywh[:,1] + boxes_cxcywh[:,3]/2
            # scale back
            dw,dh = dwdh
            # undo letterbox: subtract padding and divide by ratio
            xyxy[:,0] = (xyxy[:,0] - dw) / ratio
            xyxy[:,1] = (xyxy[:,1] - dh) / ratio
            xyxy[:,2] = (xyxy[:,2] - dw) / ratio
            xyxy[:,3] = (xyxy[:,3] - dh) / ratio
            # NMS per class? Do class-agnostic NMS for now, or grouped
            # We'll do per-class NMS to avoid suppressing different classes overlapping
            # For simplicity, if class filter empty, group per class; else global
            keep_indices = []
            # Do NMS for each class separately then merge
            unique_classes = np.unique(class_ids)
            for cls in unique_classes:
                cls_mask = class_ids == cls
                cls_boxes = xyxy[cls_mask]
                cls_scores = max_scores[cls_mask]
                cls_idx_local = np.where(cls_mask)[0]
                nms_keep = nms_boxes(cls_boxes, cls_scores, self.iou_thres, self.max_det)
                for k in nms_keep:
                    keep_indices.append(cls_idx_local[k])
            if not keep_indices:
                return detections
            # limit
            # sort by score
            keep_indices = sorted(keep_indices, key=lambda i: max_scores[np.where(np.array(keep_indices)==i)[0][0]] if False else max_scores[list(class_ids).index(class_ids[i])] if False else 0, reverse=True)
            # Instead sort by score of original
            scored = [(i, max_scores[np.where(class_ids==class_ids[i])[0].tolist().index(i) if i in np.where(class_ids==class_ids[i])[0] else 0]) for i in keep_indices]
            # Simpler: build arrays after mask then keep
            # Let's re-implement simpler: we already have filtered arrays; we need mapping
            # For correct sorting, just sort keep_indices by their score
            keep_indices = sorted(keep_indices, key=lambda idx: max_scores[np.where(np.array([*range(len(class_ids))])==idx)[0][0]] if False else max_scores[list(range(len(class_ids)))[idx]] if False else max_scores[idx] if idx < len(max_scores) else 0, reverse=True)
            # Actually max_scores and class_ids are filtered; indices refer to filtered array? No cls_idx_local maps to filtered.
            # Let's redo properly simpler method:
            # We'll rebuild detection after NMS easier: for each class group do NMS and directly create detections.
            # So return early and rebuild...

            # To avoid confusion, redo per-class directly building detections
            detections = []
            for cls in unique_classes:
                cls_mask = class_ids == cls
                cls_boxes = xyxy[cls_mask]
                cls_scores = max_scores[cls_mask]
                nms_keep = nms_boxes(cls_boxes, cls_scores, self.iou_thres, self.max_det)
                for ki in nms_keep:
                    x1,y1,x2,y2 = cls_boxes[ki]
                    # clip
                    x1 = max(0, min(x1, orig_w-1))
                    y1 = max(0, min(y1, orig_h-1))
                    x2 = max(0, min(x2, orig_w-1))
                    y2 = max(0, min(y2, orig_h-1))
                    if x2<=x1 or y2<=y1:
                        continue
                    conf = float(cls_scores[ki])
                    cid = int(cls)
                    cname = self.class_names[cid] if cid < len(self.class_names) else str(cid)
                    xyxy_tuple = (float(x1),float(y1),float(x2),float(y2))
                    xywh_tuple = xyxy_to_xywh(*xyxy_tuple)
                    norm_tuple = xyxy_to_cxcywh_norm(*xyxy_tuple, orig_w, orig_h)
                    cx = (x1+x2)/2
                    cy = (y1+y2)/2
                    area = (x2-x1)*(y2-y1)
                    ar = (x2-x1)/max(1.0,(y2-y1))
                    det = Detection(
                        class_id=cid,
                        class_name=cname,
                        confidence=conf,
                        xyxy=xyxy_tuple,
                        xywh=xywh_tuple,
                        xywh_norm=norm_tuple,
                        center=(cx,cy),
                        area=area,
                        aspect_ratio=ar,
                        track_id=-1,
                        frame_id=frame_id,
                        model_name=self.model_name,
                        inference_time_ms=inference_time
                    )
                    detections.append(det)
            # sort by confidence
            detections = sorted(detections, key=lambda d: d.confidence, reverse=True)[:self.max_det]
            return detections

        elif pred.ndim == 3 or pred.ndim==2:
            # YOLOv5 style: (1,25200,85)
            if pred.ndim==2:
                pred = np.expand_dims(pred,0)
            pred = pred[0]  # N,85
            # 0-3 xywh, 4 obj conf, 5-84 class scores
            # Some models have 4+classes directly (YOLOv8 with obj folded?)
            if pred.shape[1] > 6:
                # v5
                obj_conf = pred[:,4]
                class_scores = pred[:,5:]
                max_cls_scores = np.max(class_scores, axis=1)
                class_ids = np.argmax(class_scores, axis=1)
                confs = obj_conf * max_cls_scores
                mask = confs >= self.conf_thres
                if self.classes:
                    mask = mask & np.isin(class_ids, self.classes)
                pred = pred[mask]
                confs = confs[mask]
                class_ids = class_ids[mask]
                boxes_cxcywh = pred[:,:4]
                xyxy = np.zeros_like(boxes_cxcywh)
                xyxy[:,0] = boxes_cxcywh[:,0] - boxes_cxcywh[:,2]/2
                xyxy[:,1] = boxes_cxcywh[:,1] - boxes_cxcywh[:,3]/2
                xyxy[:,2] = boxes_cxcywh[:,0] + boxes_cxcywh[:,2]/2
                xyxy[:,3] = boxes_cxcywh[:,1] + boxes_cxcywh[:,3]/2
                dw,dh = dwdh
                xyxy[:,0] = (xyxy[:,0] - dw)/ratio
                xyxy[:,1] = (xyxy[:,1] - dh)/ratio
                xyxy[:,2] = (xyxy[:,2] - dw)/ratio
                xyxy[:,3] = (xyxy[:,3] - dh)/ratio
                # NMS per class
                unique_classes = np.unique(class_ids)
                detections=[]
                for cls in unique_classes:
                    cm = class_ids==cls
                    cb = xyxy[cm]
                    cs = confs[cm]
                    keep = nms_boxes(cb, cs, self.iou_thres, self.max_det)
                    for ki in keep:
                        x1,y1,x2,y2 = cb[ki]
                        x1 = max(0,min(x1,orig_w-1)); y1=max(0,min(y1,orig_h-1)); x2=max(0,min(x2,orig_w-1)); y2=max(0,min(y2,orig_h-1))
                        if x2<=x1 or y2<=y1: continue
                        conf=float(cs[ki]); cid=int(cls)
                        cname=self.class_names[cid] if cid<len(self.class_names) else str(cid)
                        xyxy_t=(float(x1),float(y1),float(x2),float(y2))
                        xywh_t=xyxy_to_xywh(*xyxy_t)
                        norm_t=xyxy_to_cxcywh_norm(*xyxy_t,orig_w,orig_h)
                        det=Detection(cid,cname,conf,xyxy_t,xywh_t,norm_t,((x1+x2)/2,(y1+y2)/2),(x2-x1)*(y2-y1),(x2-x1)/max(1,y2-y1),-1,frame_id,self.model_name,inference_time)
                        detections.append(det)
                detections=sorted(detections,key=lambda d:d.confidence,reverse=True)[:self.max_det]
                return detections
        return []

    def detect(self, frame: np.ndarray, frame_id: int = 0) -> FrameResult:
        if self.session is None:
            self.load()
        t0 = time.time()
        inp,ratio,dwdh,orig_shape = self._preprocess(frame)
        pre_t = time.time()
        outputs = self.session.run(self.output_names, {self.input_name: inp})
        inf_t = time.time()
        inference_time = (inf_t - pre_t)*1000.0
        dets = self._postprocess(outputs, ratio, dwdh, orig_shape, frame_id, inference_time)
        total = (time.time()-t0)*1000.0
        return FrameResult(frame_id=frame_id, width=frame.shape[1], height=frame.shape[0], detections=dets, inference_time_ms=inference_time, timestamp_unix=time.time())
