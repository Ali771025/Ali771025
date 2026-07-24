import sys
sys.path.insert(0, "python")
from yolo_monitor.utils.secrets import mask_url, expand_source_with_secrets

def test_mask():
    url="rtsp://user:mypass@192.168.1.10:554/stream"
    masked=mask_url(url)
    assert "mypass" not in masked
    assert "****" in masked

def test_expand():
    import os
    os.environ["CAMERA_USER"]="admin"
    os.environ["CAMERA_PASSWORD"]="secret"
    src="rtsp://CAMERA_USER:CAMERA_PASSWORD@192.168.1.10/stream"
    expanded=expand_source_with_secrets(src)
    assert "admin" in expanded
    assert "secret" in expanded
