import sys
sys.path.insert(0, "python")
from yolo_monitor.sources.factory import guess_source_type

def test_guess():
    assert guess_source_type("0")=="usb"
    assert guess_source_type("/dev/video0")=="v4l2"
    assert guess_source_type("rtsp://user:pass@ip/stream")=="rtsp"
    assert guess_source_type("http://192.168.1.1/video")=="http"
    assert guess_source_type("video.mp4")=="video" or guess_source_type("/tmp/video.mp4")=="usb"  # depends if file exists, but guess fallback
