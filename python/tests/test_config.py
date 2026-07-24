import sys
sys.path.insert(0, "python")
from yolo_monitor.config import AppConfig

def test_default():
    cfg=AppConfig()
    assert cfg.imgsz==640

def test_merge():
    cfg=AppConfig()
    cfg2=cfg.merge_cli(**{"conf_thres":0.5})
    assert cfg2.conf_thres==0.5
