from __future__ import annotations
from typing import List, Tuple, Optional
import numpy as np
import cv2

class SAMHelper:
    def __init__(self, model_path: Optional[str] = None, device: str = "cpu"):
        self.model_path = model_path
        self.device = device
        self.session = None
        self.loaded = False
        if model_path:
            self.try_load(model_path)

    def try_load(self, model_path: str):
        try:
            import onnxruntime as ort
            from pathlib import Path
            if not Path(model_path).exists():
                print(f"SAM model not found: {model_path}, fallback to GrabCut")
                return False
            providers = ["CPUExecutionProvider"]
            if self.device.startswith("cuda"):
                providers = ["CUDAExecutionProvider","CPUExecutionProvider"]
            self.session = ort.InferenceSession(model_path, providers=providers)
            self.loaded = True
            return True
        except Exception as e:
            print(f"SAM load failed: {e}, fallback to GrabCut")
            self.loaded=False
            return False

    def box_to_mask(self, image: np.ndarray, box: Tuple[float,float,float,float]) -> np.ndarray:
        # if SAM loaded, run inference, else GrabCut
        if self.loaded and self.session:
            try:
                return self._sam_inference(image, box)
            except Exception as e:
                print(f"SAM inference failed: {e}, fallback GrabCut")
        return self._grabcut_mask(image, box)

    def _sam_inference(self, image: np.ndarray, box: Tuple[float,float,float,float]) -> np.ndarray:
        # Simplified SAM ONNX inference - assumes MobileSAM format
        # This is a stub; real SAM needs image embedding + prompt
        # For offline demo, fallback to grabcut
        return self._grabcut_mask(image, box)

    def _grabcut_mask(self, image: np.ndarray, box: Tuple[float,float,float,float]) -> np.ndarray:
        x1,y1,x2,y2 = map(int, box)
        x1 = max(0,x1); y1=max(0,y1); x2=min(image.shape[1]-1,x2); y2=min(image.shape[0]-1,y2)
        if x2<=x1 or y2<=y1:
            return np.zeros((image.shape[0], image.shape[1]), dtype=np.uint8)
        mask = np.zeros((image.shape[0], image.shape[1]), dtype=np.uint8)
        bgdModel = np.zeros((1,65), np.float64)
        fgdModel = np.zeros((1,65), np.float64)
        rect = (x1,y1,x2-x1,y2-y1)
        try:
            cv2.grabCut(image, mask, rect, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_RECT)
            mask2 = np.where((mask==2)|(mask==0),0,1).astype('uint8')
            return mask2*255
        except Exception:
            # fallback: just fill box
            mask[y1:y2, x1:x2]=255
            return mask

    def click_to_mask(self, image: np.ndarray, points: List[Tuple[int,int]], labels: List[int]) -> np.ndarray:
        # points: list of (x,y), labels 1=fg 0=bg
        if self.loaded:
            return self.box_to_mask(image, (0,0,image.shape[1],image.shape[0]))
        # simple: use grabcut with points?
        mask = np.zeros((image.shape[0], image.shape[1]), dtype=np.uint8)
        for (x,y), lbl in zip(points, labels):
            if lbl==1:
                cv2.circle(mask,(x,y),10,255,-1)
        return mask
