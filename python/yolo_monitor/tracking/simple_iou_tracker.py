from __future__ import annotations
from typing import List, Dict, Tuple
import numpy as np
from ..detectors.base import Detection

def iou(box1: Tuple[float,float,float,float], box2: Tuple[float,float,float,float]) -> float:
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    if x2<=x1 or y2<=y1:
        return 0.0
    inter = (x2-x1)*(y2-y1)
    a1 = (box1[2]-box1[0])*(box1[3]-box1[1])
    a2 = (box2[2]-box2[0])*(box2[3]-box2[1])
    union = a1+a2-inter
    if union<=0:
        return 0.0
    return inter/union

class Track:
    def __init__(self, track_id: int, det: Detection):
        self.track_id = track_id
        self.box = det.xyxy
        self.class_id = det.class_id
        self.age = 0
        self.hits = 1

class IOUTracker:
    def __init__(self, iou_threshold: float = 0.3, max_age: int = 30, min_hits: int = 1):
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self.min_hits = min_hits
        self.tracks: Dict[int, Track] = {}
        self.next_id = 0

    def update(self, detections: List[Detection]) -> List[Detection]:
        # simple greedy IoU matching
        if not self.tracks:
            for det in detections:
                det.track_id = self.next_id
                self.tracks[self.next_id] = Track(self.next_id, det)
                self.next_id+=1
            return detections

        track_ids = list(self.tracks.keys())
        track_boxes = [self.tracks[tid].box for tid in track_ids]

        # compute iou matrix
        unmatched_dets = list(range(len(detections)))
        matched = {}
        # for each track, find best det
        for ti, tbox in enumerate(track_boxes):
            best_iou = 0
            best_j = -1
            for j in unmatched_dets:
                dbox = detections[j].xyxy
                # only match same class if possible
                if detections[j].class_id != self.tracks[track_ids[ti]].class_id:
                    continue
                cur_iou = iou(tbox, dbox)
                if cur_iou > best_iou and cur_iou >= self.iou_threshold:
                    best_iou = cur_iou
                    best_j = j
            if best_j != -1:
                tid = track_ids[ti]
                detections[best_j].track_id = tid
                self.tracks[tid].box = detections[best_j].xyxy
                self.tracks[tid].age = 0
                self.tracks[tid].hits +=1
                matched[best_j]=tid
                if best_j in unmatched_dets:
                    unmatched_dets.remove(best_j)

        # new tracks for unmatched
        for j in unmatched_dets:
            det = detections[j]
            det.track_id = self.next_id
            self.tracks[self.next_id]=Track(self.next_id, det)
            self.next_id+=1

        # age old tracks
        to_delete = []
        for tid in self.tracks:
            if tid not in matched.values():
                self.tracks[tid].age+=1
            if self.tracks[tid].age > self.max_age:
                to_delete.append(tid)
        for tid in to_delete:
            del self.tracks[tid]

        return detections
