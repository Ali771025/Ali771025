from __future__ import annotations
from typing import List, Optional, Tuple
import cv2
import numpy as np

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPoint, QRect, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QMouseEvent, QWheelEvent

from ..core.annotation import AnnotationObject
from ..utils.colors import get_color

class AnnotationCanvas(QWidget):
    selectionChanged = Signal(object)
    objectCreated = Signal(object)
    objectModified = Signal(object)
    objectDeleted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.image: Optional[np.ndarray] = None
        self.qpixmap: Optional[QPixmap] = None
        self.objects: List[AnnotationObject] = []
        self.selected_id: Optional[str] = None
        self.class_names: List[str] = []
        self.zoom = 1.0
        self.offset = QPoint(0,0)
        self.drag_start = None
        self.drag_mode = None
        self.current_rect = None
        self.setMinimumSize(640,480)
        self.panning = False
        self.pan_start = None
        self.crosshair = True

    def set_image(self, img: np.ndarray, objects: List[AnnotationObject], class_names: List[str]):
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
        qimg = qimg.copy()
        self.qpixmap = QPixmap.fromImage(qimg)

    def _image_to_canvas(self, ix, iy):
        if not self.qpixmap:
            return 0,0
        img_w = int(self.qpixmap.width()*self.zoom)
        img_h = int(self.qpixmap.height()*self.zoom)
        x_offset = (self.width()-img_w)//2 + self.offset.x()
        y_offset = (self.height()-img_h)//2 + self.offset.y()
        cx = x_offset + int(ix*self.zoom)
        cy = y_offset + int(iy*self.zoom)
        return cx, cy

    def _canvas_to_image(self, cx, cy):
        if not self.qpixmap:
            return 0,0
        img_w = int(self.qpixmap.width()*self.zoom)
        img_h = int(self.qpixmap.height()*self.zoom)
        x_offset = (self.width()-img_w)//2 + self.offset.x()
        y_offset = (self.height()-img_h)//2 + self.offset.y()
        ix = (cx - x_offset)/self.zoom
        iy = (cy - y_offset)/self.zoom
        return ix, iy

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(30,30,30))
        if self.qpixmap is None:
            painter.setPen(QPen(QColor(200,200,200)))
            painter.drawText(self.rect(), Qt.AlignCenter, "No image - Import folder or video")
            return
        img_w = int(self.qpixmap.width()*self.zoom)
        img_h = int(self.qpixmap.height()*self.zoom)
        x_offset = (self.width()-img_w)//2 + self.offset.x()
        y_offset = (self.height()-img_h)//2 + self.offset.y()
        target_rect = QRect(x_offset, y_offset, img_w, img_h)
        painter.drawPixmap(target_rect, self.qpixmap)

        # grid/crosshair optional
        if self.crosshair:
            painter.setPen(QPen(QColor(60,60,60),1,Qt.DotLine))
            # center lines
            painter.drawLine(x_offset, self.height()//2, x_offset+img_w, self.height()//2)
            painter.drawLine(self.width()//2, y_offset, self.width()//2, y_offset+img_h)

        for obj in self.objects:
            if not obj.visible:
                continue
            x1,y1,x2,y2 = obj.bbox_xyxy
            sx1 = x_offset + int(x1*self.zoom)
            sy1 = y_offset + int(y1*self.zoom)
            sx2 = x_offset + int(x2*self.zoom)
            sy2 = y_offset + int(y2*self.zoom)
            r,g,b = get_color(obj.class_id)
            qcolor = QColor(r,g,b)
            if obj.is_ai:
                # AI boxes dashed with transparency
                qcolor.setAlpha(180)
            pen_width = 3 if obj.id==self.selected_id else 2
            style = Qt.SolidLine if not obj.is_ai else Qt.DashLine
            painter.setPen(QPen(qcolor, pen_width, style))
            painter.drawRect(QRect(QPoint(sx1,sy1), QPoint(sx2,sy2)))
            # label
            label = f"{obj.class_name} {obj.confidence*100:.0f}%" if obj.is_ai else obj.class_name
            if obj.id==self.selected_id:
                label += " [SELECTED]"
            painter.setPen(QPen(QColor(255,255,255)))
            # background for text
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(label)
            th = fm.height()
            painter.fillRect(QRect(sx1, max(0,sy1-th-4), tw+8, th+4), QColor(r,g,b,200))
            painter.setPen(QPen(QColor(255,255,255)))
            painter.drawText(sx1+4, sy1-5 if sy1>15 else sy1+15, label)
            if obj.id==self.selected_id:
                painter.setPen(QPen(QColor(255,255,255),1))
                hs=7
                for cx,cy in [(sx1,sy1),(sx2,sy1),(sx1,sy2),(sx2,sy2)]:
                    painter.fillRect(QRect(cx-hs//2, cy-hs//2, hs, hs), QColor(255,255,255))
                    painter.drawRect(QRect(cx-hs//2, cy-hs//2, hs, hs))

        if self.current_rect:
            painter.setPen(QPen(QColor(0,255,0),2,Qt.DashLine))
            painter.drawRect(self.current_rect)

    def mousePressEvent(self, event: QMouseEvent):
        if self.image is None or self.qpixmap is None:
            return
        pos = event.position() if hasattr(event,'position') else event.pos()
        x,y = int(pos.x()), int(pos.y())
        ix,iy = self._canvas_to_image(x,y)

        if event.button()==Qt.MiddleButton or (event.button()==Qt.LeftButton and event.modifiers() & Qt.ControlModifier):
            self.panning=True
            self.pan_start = QPoint(x,y)
            return

        if event.button()==Qt.LeftButton:
            # check existing object
            clicked_obj = None
            # reverse order: top-most first
            for obj in reversed(self.objects):
                x1,y1,x2,y2 = obj.bbox_xyxy
                if x1<=ix<=x2 and y1<=iy<=y2:
                    clicked_obj = obj
                    break
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
            # delete or context? For now select and show delete hint
            clicked_obj = None
            for obj in reversed(self.objects):
                x1,y1,x2,y2 = obj.bbox_xyxy
                if x1<=ix<=x2 and y1<=iy<=y2:
                    clicked_obj = obj
                    break
            if clicked_obj:
                self.selected_id = clicked_obj.id
                self.selectionChanged.emit(clicked_obj)
                self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.position() if hasattr(event,'position') else event.pos()
        x,y = int(pos.x()), int(pos.y())

        if self.panning and self.pan_start:
            delta = QPoint(x,y) - self.pan_start
            self.offset += delta
            self.pan_start = QPoint(x,y)
            self.update()
            return

        if self.drag_mode is None:
            self.update()
            return

        ix,iy = self._canvas_to_image(x,y)

        if self.drag_mode=="create" and self.drag_start:
            sx,sy = self.drag_start
            x1 = min(sx, ix); y1=min(sy,iy); x2=max(sx,ix); y2=max(sy,iy)
            # to canvas rect
            csx,csy = self._image_to_canvas(x1,y1)
            cex,cey = self._image_to_canvas(x2,y2)
            self.current_rect=QRect(int(csx), int(csy), int(cex-csx), int(cey-csy))
            self.update()
        elif self.drag_mode=="move" and self.drag_start:
            orig_ix, orig_iy, orig_bbox = self.drag_start
            dx = ix - orig_ix
            dy = iy - orig_iy
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
        if self.panning:
            self.panning=False
            self.pan_start=None
            return
        if self.drag_mode=="create" and self.drag_start:
            pos = event.position() if hasattr(event,'position') else event.pos()
            x,y = int(pos.x()), int(pos.y())
            ix,iy = self._canvas_to_image(x,y)
            sx,sy=self.drag_start
            x1,y1=min(sx,ix), min(sy,iy)
            x2,y2=max(sx,ix), max(sy,iy)
            if abs(x2-x1)>5 and abs(y2-y1)>5:
                from ..core.annotation import AnnotationObject
                # clip to image bounds
                if self.image is not None:
                    h,w = self.image.shape[:2]
                    x1 = max(0,min(x1,w-1)); y1=max(0,min(y1,h-1)); x2=max(0,min(x2,w-1)); y2=max(0,min(y2,h-1))
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
        delta = event.angleDelta().y()
        old_zoom = self.zoom
        if delta>0:
            self.zoom = min(10.0, self.zoom*1.1)
        else:
            self.zoom = max(0.1, self.zoom*0.9)
        # zoom towards mouse position
        pos = event.position() if hasattr(event,'position') else event.pos()
        # adjust offset to keep mouse point stable (optional)
        self.update()

    def keyPressEvent(self, event):
        if event.key()==Qt.Key_Delete:
            if self.selected_id:
                self.objectDeleted.emit(self.selected_id)
        super().keyPressEvent(event)
