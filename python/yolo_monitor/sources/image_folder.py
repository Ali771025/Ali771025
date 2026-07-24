from __future__ import annotations
from pathlib import Path
from typing import List, Tuple, Optional
import cv2
import numpy as np
from .base import BaseSource

class ImageFolderSource(BaseSource):
    def __init__(self, source: str, source_type="images", extensions=(".jpg",".jpeg",".png",".bmp",".tiff",".webp")):
        super().__init__(source, source_type)
        self.extensions = extensions
        self.files: List[Path] = []
        self.idx = 0

    def open(self) -> bool:
        p = Path(self.source)
        if not p.exists():
            self.last_error = f"Folder not found: {self.source}"
            return False
        if p.is_file():
            # single image treated as folder of 1
            self.files = [p]
        else:
            self.files = sorted([f for f in p.rglob("*") if f.suffix.lower() in self.extensions])
        if not self.files:
            self.last_error = f"No images found in {self.source}"
            return False
        self.idx = 0
        self.frame_id = 0
        self.is_open = True
        return True

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self.idx >= len(self.files):
            return False, None
        fp = self.files[self.idx]
        self.idx += 1
        img = cv2.imread(str(fp))
        if img is None:
            # skip corrupt
            return self.read()
        self.frame_id += 1
        self.width, self.height = img.shape[1], img.shape[0]
        return True, img

    def close(self):
        self.is_open=False

    def is_live(self) -> bool:
        return False

    def get_info(self) -> str:
        return f"images:{self.source} ({self.idx}/{len(self.files)})"
