import sys
sys.path.insert(0, "python")
from yolo_monitor.utils.geometry import xyxy_to_xywh, xywh_to_xyxy, xyxy_to_cxcywh_norm, clip_bbox

def test_xyxy_to_xywh():
    assert xyxy_to_xywh(0,0,10,20)==(0,0,10,20)

def test_clip():
    assert clip_bbox(-10,-10,1000,1000,640,480)==(0,0,639,479)

def test_norm():
    cx,cy,w,h = xyxy_to_cxcywh_norm(0,0,100,100,200,200)
    assert abs(cx-0.25)<1e-6
    assert abs(cy-0.25)<1e-6
