from __future__ import annotations
from typing import List, Optional, Tuple
import cv2
import numpy as np

try:
    from PySide6.QtWidgets import QWidget
    from PySide6.QtCore import Qt, QPoint, QRect, Signal
    from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QMouseEvent, QWheelEvent
    QT_AVAILABLE=True
except ImportError:
    QT_AVAILABLE=False

if QT_AVAILABLE:
    class AnnotationCanvas(QWidget):
        selectionChanged = Signal(object)
        objectCreated = Signal(object)
        objectModified = Signal(object)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setMouseTracking(True)
            self.image: Optional[np.ndarray] = None
            self.qpixmap: Optional[QPixmap] = None
            self.objects: List = []
            self.selected_id: Optional[str] = None
            self.class_names: List[str] = []
            self.zoom = 1.0
            self.offset = QPoint(0,0)
            self.drag_start = None
            self.drag_mode = None  # "create", "move", "resize"
            self.current_rect = None
            self.resize_handle = None
            self.setMinimumSize(640,480)

        def set_image(self, img: np.ndarray, objects: List, class_names: List[str]):
            self.image = img
            self.objects = objects
            self.class_names = class_names
            self._update_pixmap()
            self.update()

        def _update_pixmap(self):
            if self.image is None:
                self.qpixmap=None
                return
            h,w,ch = self.image.shape
            bytes_per_line = ch*w
            rgb = cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            # copy data
            qimg = qimg.copy()
            self.qpixmap = QPixmap.fromImage(qimg)

        def paintEvent(self, event):
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(30,30,30))
            if self.qpixmap is None:
                painter.setPen(QPen(QColor(200,200,200)))
                painter.drawText(self.rect(), Qt.AlignCenter, "No image")
                return
            # draw image with zoom
            img_w = int(self.qpixmap.width()*self.zoom)
            img_h = int(self.qpixmap.height()*self.zoom)
            # centered?
            x_offset = (self.width()-img_w)//2 + self.offset.x()
            y_offset = (self.height()-img_h)//2 + self.offset.y()
            target_rect = QRect(x_offset, y_offset, img_w, img_h)
            painter.drawPixmap(target_rect, self.qpixmap)

            # draw objects
            for obj in self.objects:
                if not obj.visible:
                    continue
                x1,y1,x2,y2 = obj.bbox_xyxy
                # scale to canvas
                sx1 = x_offset + int(x1*self.zoom)
                sy1 = y_offset + int(y1*self.zoom)
                sx2 = x_offset + int(x2*self.zoom)
                sy2 = y_offset + int(y2*self.zoom)
                color_idx = obj.class_id % 16
                palette = [(255,0,0),(0,255,0),(0,0,255),(255,255,0),(255,0,255),(0,255,255),(128,0,128),(255,128,0),(0,128,255),(128,255,0),(255,0,128),(0,255,128),(128,128,0),(128,0,0),(0,128,0),(0,0,128)]
                r,g,b = palette[color_idx]
                qcolor = QColor(r,g,b)
                pen_width = 3 if obj.id==self.selected_id else 2
                painter.setPen(QPen(qcolor, pen_width))
                painter.drawRect(QRect(QPoint(sx1,sy1), QPoint(sx2,sy2)))
                # label
                label = f"{obj.class_name} {obj.confidence*100:.0f}%" if obj.is_ai else obj.class_name
                painter.setPen(QPen(QColor(255,255,255)))
                painter.drawText(sx1, sy1-5 if sy1>10 else sy1+15, label)
                # resize handles if selected
                if obj.id==self.selected_id:
                    painter.setPen(QPen(QColor(255,255,255),1))
                    hs=6
                    for cx,cy in [(sx1,sy1),(sx2,sy1),(sx1,sy2),(sx2,sy2)]:
                        painter.fillRect(QRect(cx-hs//2, cy-hs//2, hs, hs), QColor(255,255,255))

            if self.current_rect:
                painter.setPen(QPen(QColor(0,255,0),2,Qt.DashLine))
                painter.drawRect(self.current_rect)

        def mousePressEvent(self, event: QMouseEvent):
            if self.image is None:
                return
            pos = event.position() if hasattr(event,'position') else event.pos()
            x,y = int(pos.x()), int(pos.y())
            # transform to image coordinates
            img_w = int(self.qpixmap.width()*self.zoom)
            img_h = int(self.qpixmap.height()*self.zoom)
            x_offset = (self.width()-img_w)//2 + self.offset.x()
            y_offset = (self.height()-img_h)//2 + self.offset.y()
            ix = (x - x_offset)/self.zoom
            iy = (y - y_offset)/self.zoom
            if event.button()==Qt.LeftButton:
                # check if clicking on existing object handle
                clicked_obj = None
                for obj in self.objects:
                    x1,y1,x2,y2 = obj.bbox_xyxy
                    if x1<=ix<=x2 and y1<=iy<=y2:
                        clicked_obj = obj
                if clicked_obj:
                    self.selected_id = clicked_obj.id
                    self.selectionChanged.emit(clicked_obj)
                    self.drag_mode="move"
                    self.drag_start=(ix,iy, clicked_obj.bbox_xyxy)
                else:
                    # start creating
                    self.drag_mode="create"
                    self.drag_start=(ix,iy)
                    self.current_rect=QRect(x,y,0,0)
                self.update()
            elif event.button()==Qt.RightButton:
                # context: select
                pass

        def mouseMoveEvent(self, event: QMouseEvent):
            if self.drag_mode is None:
                return
            pos = event.position() if hasattr(event,'position') else event.pos()
            x,y = int(pos.x()), int(pos.y())
            img_w = int(self.qpixmap.width()*self.zoom) if self.qpixmap else 1
            img_h = int(self.qpixmap.height()*self.zoom) if self.qpixmap else 1
            x_offset = (self.width()-img_w)//2 + self.offset.x()
            y_offset = (self.height()-img_h)//2 + self.offset.y()
            ix = (x - x_offset)/self.zoom
            iy = (y - y_offset)/self.zoom
            if self.drag_mode=="create" and self.drag_start:
                sx,sy = self.drag_start
                x1 = min(sx, ix); y1=min(sy,iy); x2=max(sx,ix); y2=max(sy,iy)
                self.current_rect=QRect(int(x_offset+x1*self.zoom), int(y_offset+y1*self.zoom), int((x2-x1)*self.zoom), int((y2-y1)*self.zoom))
                self.update()
            elif self.drag_mode=="move" and self.drag_start:
                orig_ix, orig_iy, orig_bbox = self.drag_start
                dx = ix - orig_ix
                dy = iy - orig_iy
                # find selected
                for obj in self.objects:
                    if obj.id==self.selected_id:
                        x1,y1,x2,y2 = orig_bbox
                        obj.bbox_xyxy=(x1+dx, y1+dy, x2+dx, y2+dy)
                        if self.image is not None:
                            h,w = self.image.shape[:2]
                            obj.update_norm(w,h)
                        self.objectModified.emit(obj)
                        break
                self.update()

        def mouseReleaseEvent(self, event: QMouseEvent):
            if self.drag_mode=="create" and self.drag_start:
                pos = event.position() if hasattr(event,'position') else event.pos()
                x,y = int(pos.x()), int(pos.y())
                img_w = int(self.qpixmap.width()*self.zoom) if self.qpixmap else 1
                img_h = int(self.qpixmap.height()*self.zoom) if self.qpixmap else 1
                x_offset = (self.width()-img_w)//2 + self.offset.x()
                y_offset = (self.height()-img_h)//2 + self.offset.y()
                ix = (x - x_offset)/self.zoom
                iy = (y - y_offset)/self.zoom
                sx,sy=self.drag_start
                x1,y1=min(sx,ix), min(sy,iy)
                x2,y2=max(sx,ix), max(sy,iy)
                if abs(x2-x1)>5 and abs(y2-y1)>5:
                    # create new object with current class
                    # emit
                    from ..core.annotation import AnnotationObject
                    obj = AnnotationObject(class_id=0, class_name=self.class_names[0] if self.class_names else "object", bbox_xyxy=(float(x1),float(y1),float(x2),float(y2)))
                    if self.image is not None:
                        h,w = self.image.shape[:2]
                        obj.update_norm(w,h)
                    self.objectCreated.emit(obj)
            self.drag_mode=None
            self.drag_start=None
            self.current_rect=None
            self.update()

        def wheelEvent(self, event: QWheelEvent):
            # zoom
            delta = event.angleDelta().y()
            if delta>0:
                self.zoom = min(10.0, self.zoom*1.1)
            else:
                self.zoom = max(0.1, self.zoom*0.9)
            self.update()

else:
    class AnnotationCanvas:
        pass
