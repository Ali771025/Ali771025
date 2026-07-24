from __future__ import annotations
import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional
import yaml
from dataclasses import asdict
from .annotation import ImageInfo, ImageAnnotations, AnnotationObject
import cv2

class AnnotationProject:
    def __init__(self, project_path: str, classes: List[str] = None, colors: List = None):
        self.project_path = Path(project_path)
        self.classes = classes or ["person","car"]
        self.colors = colors or []
        self.images: Dict[str, ImageInfo] = {}
        self.config_path = self.project_path / "project.yaml"
        self.images_dir = self.project_path / "images"
        self.labels_dir = self.project_path / "labels"
        self.backup_dir = self.project_path / ".backup"
        self.autosave = True

    @classmethod
    def create(cls, path: str, classes: List[str] = None) -> "AnnotationProject":
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        proj = cls(str(p), classes=classes)
        proj.images_dir.mkdir(parents=True, exist_ok=True)
        proj.labels_dir.mkdir(parents=True, exist_ok=True)
        proj.backup_dir.mkdir(parents=True, exist_ok=True)
        proj.save()
        return proj

    @classmethod
    def open(cls, path: str) -> "AnnotationProject":
        p = Path(path)
        config_path = p / "project.yaml"
        if not config_path.exists():
            # if path is images folder, create project around it
            if p.is_dir() and any(f.suffix.lower() in [".jpg",".jpeg",".png",".bmp"] for f in p.iterdir()):
                proj = cls.create(str(p), classes=["object"])
                proj.import_images(str(p))
                return proj
            raise FileNotFoundError(f"Project config not found: {config_path}")
        data = yaml.safe_load(config_path.read_text())
        proj = cls(str(p), classes=data.get("classes", []), colors=data.get("colors", []))
        # load images
        images_yaml = data.get("images", [])
        for img_data in images_yaml:
            # minimal reconstruction
            pass
        # scan images dir if exists
        proj.scan_images()
        return proj

    def scan_images(self):
        if not self.images_dir.exists():
            return
        exts = {".jpg",".jpeg",".png",".bmp",".webp",".tiff"}
        for f in self.images_dir.rglob("*"):
            if f.suffix.lower() in exts:
                rel = str(f)
                if rel not in self.images:
                    try:
                        img = cv2.imread(str(f))
                        h,w = img.shape[:2] if img is not None else (0,0)
                        ann = ImageAnnotations(image_path=str(f), image_id=f.stem, width=w, height=h)
                        self.images[rel] = ImageInfo(path=str(f), width=w, height=h, annotations=ann)
                    except Exception:
                        continue

    def import_images(self, folder: str, copy: bool = False):
        folder_p = Path(folder)
        exts = {".jpg",".jpeg",".png",".bmp",".webp",".tiff"}
        files = [f for f in folder_p.rglob("*") if f.suffix.lower() in exts]
        self.images_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            dest = self.images_dir / f.name
            if copy:
                try:
                    shutil.copy2(str(f), str(dest))
                    path_to_store = str(dest)
                except Exception:
                    path_to_store = str(f)
            else:
                path_to_store = str(f)
            if path_to_store not in self.images:
                img = cv2.imread(str(f))
                h,w = img.shape[:2] if img is not None else (0,0)
                ann = ImageAnnotations(image_path=path_to_store, image_id=f.stem, width=w, height=h)
                self.images[path_to_store] = ImageInfo(path=path_to_store, width=w, height=h, annotations=ann)

    def import_video(self, video_path: str, fps: float = 1.0, extract_dir: str = None):
        # extract frames
        import cv2
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video {video_path}")
        vid_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, int(vid_fps / fps)) if fps>0 else 1
        out_dir = Path(extract_dir) if extract_dir else self.images_dir / Path(video_path).stem
        out_dir.mkdir(parents=True, exist_ok=True)
        idx=0
        saved=0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % step ==0:
                out_path = out_dir / f"{Path(video_path).stem}_{saved:06d}.jpg"
                cv2.imwrite(str(out_path), frame)
                h,w = frame.shape[:2]
                ann = ImageAnnotations(image_path=str(out_path), image_id=out_path.stem, width=w, height=h)
                self.images[str(out_path)] = ImageInfo(path=str(out_path), width=w, height=h, annotations=ann)
                saved+=1
            idx+=1
        cap.release()
        return saved

    def save(self):
        data = {
            "name": self.project_path.name,
            "classes": self.classes,
            "colors": self.colors,
            "images_dir": str(self.images_dir),
            "labels_dir": str(self.labels_dir),
        }
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(yaml.safe_dump(data))
        # backup
        try:
            if self.backup_dir.exists():
                backup_file = self.backup_dir / f"project_{int(time.time())}.yaml"
                backup_file.write_text(yaml.safe_dump(data))
        except Exception:
            pass

    def get_image_list(self) -> List[ImageInfo]:
        return list(self.images.values())

import time

# history
cat > python/yolo_annotator/core/history.py <<'PY'
from __future__ import annotations
from typing import List, Any, Callable
from copy import deepcopy

class HistoryManager:
    def __init__(self, max_history: int = 100):
        self.undo_stack: List[Any] = []
        self.redo_stack: List[Any] = []
        self.max_history = max_history

    def push(self, state: Any):
        self.undo_stack.append(deepcopy(state))
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self) -> Any:
        if not self.undo_stack:
            return None
        state = self.undo_stack.pop()
        self.redo_stack.append(state)
        return self.undo_stack[-1] if self.undo_stack else None

    def redo(self) -> Any:
        if not self.redo_stack:
            return None
        state = self.redo_stack.pop()
        self.undo_stack.append(state)
        return state

    def can_undo(self) -> bool:
        return len(self.undo_stack)>0

    def can_redo(self) -> bool:
        return len(self.redo_stack)>0
