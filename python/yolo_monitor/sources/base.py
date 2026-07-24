from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Iterator
import cv2
import numpy as np

class BaseSource(ABC):
    def __init__(self, source: str, source_type: str = "auto"):
        self.source = source
        self.source_type = source_type
        self.width = 0
        self.height = 0
        self.fps = 30.0
        self.is_open = False
        self.frame_id = 0
        self.last_error: Optional[str] = None

    @abstractmethod
    def open(self) -> bool:
        pass

    @abstractmethod
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        pass

    @abstractmethod
    def close(self):
        pass

    def get_info(self) -> str:
        return f"{self.source_type}:{self.source}"

    def get_resolution(self) -> Tuple[int,int]:
        return self.width, self.height

    def __iter__(self) -> Iterator[np.ndarray]:
        self.open()
        while True:
            ok, frame = self.read()
            if not ok:
                break
            yield frame
        self.close()

    def is_live(self) -> bool:
        # live streams should attempt reconnect
        return self.source_type in ("usb","v4l2","rtsp","http","rtmp","gstreamer")

class OpenCVSource(BaseSource):
    def __init__(self, source, source_type="auto", backend=None, width=None, height=None):
        super().__init__(source, source_type)
        self.backend = backend
        self.cap: Optional[cv2.VideoCapture] = None
        self.req_width = width
        self.req_height = height

    def open(self) -> bool:
        try:
            # determine opencv source
            src = self.source
            # numeric string -> int
            if isinstance(src, str) and src.isdigit():
                src = int(src)
            # check for dshow://
            # opencv handles rtsp, http, file directly
            if self.backend == "gstreamer":
                self.cap = cv2.VideoCapture(src, cv2.CAP_GSTREAMER)
            else:
                # try default, with fallback
                self.cap = cv2.VideoCapture(src)
            if not self.cap or not self.cap.isOpened():
                self.last_error = f"Failed to open {src}"
                return False
            if self.req_width:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.req_width)
            if self.req_height:
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.req_height)
            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
            self.is_open = True
            self.frame_id = 0
            return True
        except Exception as e:
            self.last_error = str(e)
            return False

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self.cap:
            return False, None
        ret, frame = self.cap.read()
        if ret and frame is not None:
            self.frame_id += 1
            self.width, self.height = frame.shape[1], frame.shape[0]
            return True, frame
        else:
            return False, None

    def close(self):
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
        self.cap = None
        self.is_open = False
