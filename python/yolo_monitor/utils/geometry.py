from __future__ import annotations
from typing import Tuple

def xyxy_to_xywh(x1: float, y1: float, x2: float, y2: float) -> Tuple[float,float,float,float]:
    return (x1, y1, x2-x1, y2-y1)

def xywh_to_xyxy(x: float, y: float, w: float, h: float) -> Tuple[float,float,float,float]:
    return (x, y, x+w, y+h)

def xyxy_to_cxcywh_norm(x1: float, y1: float, x2: float, y2: float, img_w: int, img_h: int) -> Tuple[float,float,float,float]:
    cx = ((x1+x2)/2.0)/img_w if img_w else 0
    cy = ((y1+y2)/2.0)/img_h if img_h else 0
    w = (x2-x1)/img_w if img_w else 0
    h = (y2-y1)/img_h if img_h else 0
    return (cx,cy,w,h)

def clip_bbox(x1: float, y1: float, x2: float, y2: float, w: int, h: int) -> Tuple[float,float,float,float]:
    x1 = max(0, min(x1, w-1))
    y1 = max(0, min(y1, h-1))
    x2 = max(0, min(x2, w-1))
    y2 = max(0, min(y2, h-1))
    if x2 < x1:
        x1,x2 = x2,x1
    if y2 < y1:
        y1,y2 = y2,y1
    return (x1,y1,x2,y2)

def area_xyxy(x1: float, y1: float, x2: float, y2: float) -> float:
    return max(0.0, x2-x1) * max(0.0, y2-y1)
