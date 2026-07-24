from __future__ import annotations
import time
from pathlib import Path
from typing import List, Optional
import cv2
import numpy as np

from ..core.annotation import AnnotationObject
from ..utils.geometry import xyxy_to_xywh, xyxy_to_cxcywh_norm

COCO_CLASSES = ["person","bicycle","car","motorcycle","airplane","bus","train","truck","boat","traffic light","fire hydrant","stop sign","parking meter","bench","bird","cat","dog","horse","sheep","cow","elephant","bear","zebra","giraffe","backpack","umbrella","handbag","tie","suitcase","frisbee","skis","snowboard","sports ball","kite","baseball bat","baseball glove","skateboard","surfboard","tennis racket","bottle","wine glass","cup","fork","knife","spoon","bowl","banana","apple","sandwich","orange","broccoli","carrot","hot dog","pizza","donut","cake","chair","couch","potted plant","bed","dining table","toilet","tv","laptop","mouse","remote","keyboard","cell phone","microwave","oven","toaster","sink","refrigerator","book","clock","vase","scissors","teddy bear","hair drier","toothbrush"]

def nms_boxes(boxes: np.ndarray, scores: np.ndarray, iou_thres: float = 0.45, max_det: int = 300):
    import cv2
    if len(boxes)==0:
        return []
    tlwh = []
    for b in boxes:
        x1,y1,x2,y2 = b
        tlwh.append([float(x1),float(y1),float(x2-x1),float(y2-y1)])
    indices = cv2.dnn.NMSBoxes(tlwh, scores.tolist(), score_threshold=0.0, nms_threshold=iou_thres)
    if len(indices)==0:
        return []
    indices = indices.flatten() if hasattr(indices,'flatten') else [i[0] for i in indices]
    sorted_idx = sorted(indices, key=lambda i: scores[i], reverse=True)[:max_det]
    return sorted_idx

class YOLODetector:
    """
    Offline YOLO ONNX detector - professional, with wanted classes filtering.
    Supports auto device, CUDA, CPU, half.
    """
    def __init__(self, model_path: str, device: str = "auto", imgsz: int = 640, conf_thres: float = 0.35, iou_thres: float = 0.45, max_det: int = 300, classes: Optional[List[int]] = None, class_names: Optional[List[str]] = None, half: bool = False, wanted_classes: Optional[List[str]] = None):
        self.model_path = model_path
        self.device = device
        self.imgsz = imgsz
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres
        self.max_det = max_det
        self.classes = classes or []
        self.class_names = class_names or COCO_CLASSES.copy()
        self.half = half
        self.wanted_classes = set(wanted_classes) if wanted_classes else set()
        self.wanted_class_ids: set = set()
        if self.wanted_classes:
            for w in self.wanted_classes:
                if w in self.class_names:
                    self.wanted_class_ids.add(self.class_names.index(w))
        self.session = None
        self.input_name = None
        self.output_names = None

    def load(self):
        try:
            import onnxruntime as ort
        except ImportError:
            raise ImportError("onnxruntime not installed. pip install onnxruntime or onnxruntime-gpu")
        p = Path(self.model_path)
        if not p.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}. Run scripts/download_models.py")
        providers = []
        dev = self.device.lower()
        if dev in ("cuda","cuda:0","gpu") or dev.startswith("cuda"):
            providers = ["CUDAExecutionProvider","CPUExecutionProvider"]
        elif dev == "auto":
            try:
                avail = ort.get_available_providers()
                if "CUDAExecutionProvider" in avail:
                    providers = ["CUDAExecutionProvider","CPUExecutionProvider"]
                else:
                    providers = ["CPUExecutionProvider"]
            except Exception:
                providers = ["CPUExecutionProvider"]
        else:
            providers = ["CPUExecutionProvider"]
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(str(p), sess_options=so, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        # try yaml names
        yaml_path = p.with_suffix(".yaml")
        if yaml_path.exists():
            try:
                import yaml
                data = yaml.safe_load(yaml_path.read_text())
                if "names" in data:
                    self.class_names = list(data["names"].values()) if isinstance(data["names"], dict) else data["names"]
            except Exception:
                pass
        print(f"[YOLO] Loaded {p.name} providers={self.session.get_providers()} classes={len(self.class_names)}")

    def warmup(self, iters: int = 5):
        if self.session is None:
            self.load()
        dummy = np.zeros((self.imgsz, self.imgsz, 3), dtype=np.uint8)
        for _ in range(iters):
            self.detect_image(dummy)

    def _preprocess(self, frame: np.ndarray):
        h,w = frame.shape[:2]
        r = min(self.imgsz / h, self.imgsz / w)
        new_unpad = (int(round(w*r)), int(round(h*r)))
        dw, dh = self.imgsz - new_unpad[0], self.imgsz - new_unpad[1]
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

    def _postprocess(self, outputs, ratio, dwdh, orig_shape, inference_time):
        pred = outputs[0]
        orig_h, orig_w = orig_shape
        detections: List[AnnotationObject] = []
        if pred.ndim == 3:
            if pred.shape[1] < pred.shape[2]:
                pred = np.transpose(pred, (0,2,1))
            pred = pred[0]  # (8400,84)
            boxes_cxcywh = pred[:, :4]
            scores = pred[:, 4:]
            max_scores = np.max(scores, axis=1)
            class_ids = np.argmax(scores, axis=1)
            mask = max_scores >= self.conf_thres
            if self.classes:
                mask = mask & np.isin(class_ids, self.classes)
            if self.wanted_class_ids:
                mask = mask & np.isin(class_ids, list(self.wanted_class_ids))
            boxes_cxcywh = boxes_cxcywh[mask]
            max_scores = max_scores[mask]
            class_ids = class_ids[mask]
            xyxy = np.zeros_like(boxes_cxcywh)
            xyxy[:,0] = boxes_cxcywh[:,0] - boxes_cxcywh[:,2]/2
            xyxy[:,1] = boxes_cxcywh[:,1] - boxes_cxcywh[:,3]/2
            xyxy[:,2] = boxes_cxcywh[:,0] + boxes_cxcywh[:,2]/2
            xyxy[:,3] = boxes_cxcywh[:,1] + boxes_cxcywh[:,3]/2
            dw,dh = dwdh
            xyxy[:,0] = (xyxy[:,0] - dw) / ratio
            xyxy[:,1] = (xyxy[:,1] - dh) / ratio
            xyxy[:,2] = (xyxy[:,2] - dw) / ratio
            xyxy[:,3] = (xyxy[:,3] - dh) / ratio
            unique_classes = np.unique(class_ids)
            detections_tmp = []
            for cls in unique_classes:
                cls_mask = class_ids == cls
                cls_boxes = xyxy[cls_mask]
                cls_scores = max_scores[cls_mask]
                nms_keep = nms_boxes(cls_boxes, cls_scores, self.iou_thres, self.max_det)
                for ki in nms_keep:
                    x1,y1,x2,y2 = cls_boxes[ki]
                    x1 = max(0, min(x1, orig_w-1)); y1 = max(0, min(y1, orig_h-1))
                    x2 = max(0, min(x2, orig_w-1)); y2 = max(0, min(y2, orig_h-1))
                    if x2<=x1 or y2<=y1: continue
                    conf = float(cls_scores[ki]); cid = int(cls)
                    cname = self.class_names[cid] if cid < len(self.class_names) else str(cid)
                    if self.wanted_classes and cname not in self.wanted_classes and cid not in self.wanted_class_ids:
                        continue
                    cx = ((x1+x2)/2)/orig_w; cy = ((y1+y2)/2)/orig_h
                    bw = (x2-x1)/orig_w; bh = (y2-y1)/orig_h
                    obj = AnnotationObject(
                        class_id=cid, class_name=cname,
                        bbox_xyxy=(float(x1),float(y1),float(x2),float(y2)),
                        bbox_xywh_norm=(float(cx),float(cy),float(bw),float(bh)),
                        confidence=conf, is_ai=True, area=float((x2-x1)*(y2-y1))
                    )
                    detections_tmp.append(obj)
            detections = sorted(detections_tmp, key=lambda o: o.confidence, reverse=True)[:self.max_det]
        return detections

    def detect_image(self, frame: np.ndarray) -> List[AnnotationObject]:
        if self.session is None:
            self.load()
        inp,ratio,dwdh,orig_shape = self._preprocess(frame)
        t0 = time.time()
        outputs = self.session.run(self.output_names, {self.input_name: inp})
        inf_ms = (time.time()-t0)*1000
        return self._postprocess(outputs, ratio, dwdh, orig_shape, inf_ms)

    def detect_path(self, image_path: str) -> List[AnnotationObject]:
        img = cv2.imread(image_path)
        if img is None:
            return []
        return self.detect_image(img)

    def set_wanted_classes(self, wanted: List[str]):
        self.wanted_classes = set(wanted)
        self.wanted_class_ids = set()
        for w in wanted:
            if w in self.class_names:
                self.wanted_class_ids.add(self.class_names.index(w))
