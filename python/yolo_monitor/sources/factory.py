from __future__ import annotations
from pathlib import Path
from typing import Optional
from .base import BaseSource
from .usb import UsbSource, V4L2Source
from .rtsp import RtspSource
from .http import HttpSource
from .video_file import VideoFileSource
from .image_folder import ImageFolderSource
from .gstreamer import GStreamerSource

def guess_source_type(source: str) -> str:
    s = source.strip()
    if s.isdigit():
        return "usb"
    if s.startswith("dshow://"):
        return "usb"
    if s.startswith("/dev/video"):
        return "v4l2"
    if s.startswith("rtsp://"):
        return "rtsp"
    if s.startswith("rtmp://"):
        return "rtmp"
    if s.startswith("http://") or s.startswith("https://"):
        # check extension? assume http camera
        if any(x in s.lower() for x in ["mjpeg","mjpg","video","stream"]):
            return "http"
        # if file-like http with mp4 may be video but handle as http
        return "http"
    # gstreamer pipeline detection: contains ! and spaces?
    if "!" in s and (" videoconvert" in s or " v4l2src" in s or " rtspsrc" in s):
        return "gstreamer"
    # file checks
    p = Path(s)
    if p.exists():
        if p.is_dir():
            return "images"
        ext = p.suffix.lower()
        if ext in [".mp4",".avi",".mkv",".mov",".wmv",".flv",".webm",".m4v"]:
            return "video"
        if ext in [".jpg",".jpeg",".png",".bmp",".tiff",".webp"]:
            return "images"
    return "usb"  # default fallback

def create_source(source: str, source_type: str = "auto", timeout_ms: int = 5000) -> BaseSource:
    st = source_type
    if st == "auto":
        st = guess_source_type(source)
    st = st.lower()
    if st == "usb":
        return UsbSource(source, st)
    elif st == "v4l2":
        return V4L2Source(source, st)
    elif st == "rtsp":
        return RtspSource(source, st, timeout_ms=timeout_ms)
    elif st in ("http","mjpeg"):
        return HttpSource(source, "http")
    elif st in ("rtmp",):
        # use opencv generic
        from .base import OpenCVSource
        return OpenCVSource(source, st)
    elif st == "gstreamer":
        return GStreamerSource(source, st)
    elif st == "video":
        return VideoFileSource(source, st)
    elif st == "images":
        return ImageFolderSource(source, st)
    else:
        # fallback to opencv
        from .base import OpenCVSource
        return OpenCVSource(source, st)
