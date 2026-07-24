from __future__ import annotations
from typing import List, Tuple, Optional
import numpy as np
import cv2
from pathlib import Path

class SAMHelper:
    """
    Offline SAM helper for annotation:
    - If MobileSAM ONNX present, uses it (stub for now, as SAM needs embeddings)
    - Fallback to GrabCut for box-to-mask
    - Also supports point prompts
    """
    def __init__(self, model_path: Optional[str] = None, device: str = "cpu"):
        self.model_path = model_path
        self.device = device
        self.session = None
        self.loaded = False
        if model_path and Path(model_path).exists():
            self.try_load(model_path)

    def try_load(self, model_path: str) -> bool:
        try:
            import onnxruntime as ort
            providers = ["CPUExecutionProvider"]
            if self.device.startswith("cuda"):
                providers = ["CUDAExecutionProvider","CPUExecutionProvider"]
            self.session = ort.InferenceSession(model_path, providers=providers)
            self.loaded = True
            print(f"[SAM] Loaded {model_path}")
            return True
        except Exception as e:
            print(f"[SAM] Load failed {model_path}: {e}, fallback GrabCut")
            self.loaded = False
            return False

    def box_to_mask(self, image: np.ndarray, box: Tuple[float,float,float,float]) -> np.ndarray:
        if self.loaded and self.session:
            try:
                return self._sam_inference(image, box)
            except Exception as e:
                print(f"[SAM] inference failed: {e}, fallback")
        return self._grabcut_mask(image, box)

    def _sam_inference(self, image: np.ndarray, box: Tuple[float,float,float,float]) -> np.ndarray:
        # Simplified SAM ONNX still needs embedding - for professional version we fallback
        # Real MobileSAM ONNX pipeline would be implemented here
        return self._grabcut_mask(image, box)

    def _grabcut_mask(self, image: np.ndarray, box: Tuple[float,float,float,float]) -> np.ndarray:
        x1,y1,x2,y2 = map(int, box)
        h,w = image.shape[:2]
        x1 = max(0,x1); y1=max(0,y1); x2=min(w-1,x2); y2=min(h-1,y2)
        if x2<=x1 or y2<=y1:
            return np.zeros((h,w), dtype=np.uint8)
        mask = np.zeros((h,w), dtype=np.uint8)
        bgdModel = np.zeros((1,65), np.float64)
        fgdModel = np.zeros((1,65), np.float64)
        rect = (x1,y1,x2-x1,y2-y1)
        try:
            cv2.grabCut(image, mask, rect, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_RECT)
            mask2 = np.where((mask==2)|(mask==0),0,1).astype('uint8')
            return mask2*255
        except Exception:
            mask[y1:y2, x1:x2]=255
            return mask

    def point_to_mask(self, image: np.ndarray, points: List[Tuple[int,int]], labels: List[int]) -> np.ndarray:
        # labels 1=fg 0=bg
        if self.loaded:
            # real SAM would use points as prompts
            pass
        # fallback: draw points
        h,w = image.shape[:2]
        mask = np.zeros((h,w), dtype=np.uint8)
        for (x,y), lbl in zip(points, labels):
            if lbl==1:
                cv2.circle(mask,(x,y),15,255,-1)
        # expand with grabcut using bounding rect of points
        if points:
            xs = [p[0] for p in points]; ys = [p[1] for p in points]
            x1,y1,x2,y2 = min(xs), min(ys), max(xs), max(ys)
            # expand
            x1=max(0,x1-30); y1=max(0,y1-30); x2=min(w-1,x2+30); y2=min(h-1,y2+30)
            return self._grabcut_mask(image, (x1,y1,x2,y2))
        return mask

    def mask_to_polygon(self, mask: np.ndarray) -> List[List[Tuple[float,float]]]:
        """Convert mask to polygon list for COCO segmentation"""
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        polys = []
        for cnt in contours:
            if cv2.contourArea(cnt) < 50:
                continue
            epsilon = 0.005 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            poly = [(float(p[0][0]), float(p[0][1])) for p in approx]
            polys.append(poly)
        return polys
