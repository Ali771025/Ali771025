import sys, numpy as np
sys.path.insert(0, "python")
from yolo_monitor.detectors.base import nms_boxes

def test_nms():
    boxes=np.array([[0,0,10,10],[0,0,10,10],[100,100,110,110]], dtype=float)
    scores=np.array([0.9,0.8,0.7])
    keep=nms_boxes(boxes, scores, 0.5, 300)
    assert len(keep)==2
    assert 0 in keep and 2 in keep
