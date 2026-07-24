from __future__ import annotations
import cv2
from .base import OpenCVSource

class RtspSource(OpenCVSource):
    def __init__(self, source: str, source_type="rtsp", timeout_ms: int = 5000):
        super().__init__(source, source_type)
        self.timeout_ms = timeout_ms
        # OpenCV RTSP often needs FFMPEG options: we can set env or use fallback
        # Optionally set TCP transport: set env OPENCV_FFMPEG_WRITER_OPTIONS etc not needed for reading
        # We'll attempt to set CAP_PROP_OPEN_TIMEOUT_MSEC if available
    def open(self) -> bool:
        ok = super().open()
        if ok and self.cap is not None:
            try:
                # OpenCV >=4.7 supports CAP_PROP_OPEN_TIMEOUT_MSEC
                self.cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.timeout_ms)
                self.cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, self.timeout_ms)
            except Exception:
                pass
        return ok
