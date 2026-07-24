from __future__ import annotations
import json
import shutil
import time
from pathlib import Path
from typing import List, Dict, Optional, Set
import yaml
import cv2
from loguru import logger

from .annotation import ImageInfo, ImageAnnotations, AnnotationObject

class AnnotationProject:
    """
    Professional annotation project manager.
    - Supports images folder, labels folder, backup
    - Class management with colors
    - Import images, video frames
    - Wanted classes filtering
    - Autosave, backup recovery
    """

    def __init__(self, project_path: str, classes: List[str] = None, colors: List = None):
        self.project_path = Path(project_path)
        self.classes = classes or ["person", "car", "bicycle", "dog", "cat"]
        self.colors = colors or []
        self.images: Dict[str, ImageInfo] = {}  # path -> ImageInfo
        self.config_path = self.project_path / "project.yaml"
        self.images_dir = self.project_path / "images"
        self.labels_dir = self.project_path / "labels"
        self.backup_dir = self.project_path / ".backup"
        self.thumbnails_dir = self.project_path / ".thumbnails"
        self.autosave = True
        self.wanted_classes: Set[str] = set()  # empty = all
        self.wanted_class_ids: Set[int] = set()

    @classmethod
    def create(cls, path: str, classes: List[str] = None) -> "AnnotationProject":
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        proj = cls(str(p), classes=classes)
        proj.images_dir.mkdir(parents=True, exist_ok=True)
        proj.labels_dir.mkdir(parents=True, exist_ok=True)
        proj.backup_dir.mkdir(parents=True, exist_ok=True)
        proj.thumbnails_dir.mkdir(parents=True, exist_ok=True)
        proj.save()
        return proj

    @classmethod
    def open(cls, path: str) -> "AnnotationProject":
        p = Path(path)
        config_path = p / "project.yaml"
        if not config_path.exists():
            # if path is images folder, create project around it
            if p.is_dir() and any(f.suffix.lower() in [".jpg",".jpeg",".png",".bmp",".webp"] for f in p.rglob("*")):
                proj = cls.create(str(p), classes=["person","car","bicycle","dog","cat"])
                proj.import_images(str(p), copy=False)
                return proj
            raise FileNotFoundError(f"Project config not found: {config_path}")
        data = yaml.safe_load(config_path.read_text())
        proj = cls(str(p), classes=data.get("classes", []), colors=data.get("colors", []))
        proj.wanted_classes = set(data.get("wanted_classes", []))
        # scan
        proj.scan_images()
        # also try to load existing YOLO labels if any
        proj._try_load_yolo_labels()
        return proj

    def set_wanted_classes(self, wanted: List[str] | str):
        """
        Set filter for which classes to keep/label.
        Can be list of names or ids or comma string.
        """
        if isinstance(wanted, str):
            wanted = [x.strip() for x in wanted.split(",") if x.strip()]
        self.wanted_classes = set()
        self.wanted_class_ids = set()
        for w in wanted:
            if isinstance(w, int):
                self.wanted_class_ids.add(w)
            elif isinstance(w, str) and w.isdigit():
                self.wanted_class_ids.add(int(w))
            else:
                # name
                self.wanted_classes.add(w)
                # also map to id if exists
                if w in self.classes:
                    self.wanted_class_ids.add(self.classes.index(w))
        # if names provided but ids empty, fill ids
        if self.wanted_classes and not self.wanted_class_ids:
            for name in self.wanted_classes:
                if name in self.classes:
                    self.wanted_class_ids.add(self.classes.index(name))

    def is_wanted(self, class_id: int, class_name: str) -> bool:
        if not self.wanted_classes and not self.wanted_class_ids:
            return True
        if class_id in self.wanted_class_ids:
            return True
        if class_name in self.wanted_classes:
            return True
        return False

    def filter_objects_by_wanted(self, objects: List[AnnotationObject]) -> List[AnnotationObject]:
        if not self.wanted_classes and not self.wanted_class_ids:
            return objects
        return [o for o in objects if self.is_wanted(o.class_id, o.class_name)]

    def scan_images(self):
        if not self.images_dir.exists():
            # also scan project_path recursively for images if images_dir empty
            base = self.project_path
            exts = {".jpg",".jpeg",".png",".bmp",".webp",".tiff"}
            for f in base.rglob("*"):
                if f.suffix.lower() in exts and ".thumbnails" not in str(f) and ".backup" not in str(f):
                    rel = str(f)
                    if rel not in self.images:
                        try:
                            img = cv2.imread(str(f))
                            h,w = img.shape[:2] if img is not None else (0,0)
                            ann = ImageAnnotations(image_path=str(f), image_id=f.stem, width=w, height=h)
                            self.images[rel] = ImageInfo(path=str(f), width=w, height=h, annotations=ann)
                        except Exception:
                            continue
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

    def import_images(self, folder: str, copy: bool = False, recursive: bool = True) -> int:
        folder_p = Path(folder)
        if not folder_p.exists():
            raise FileNotFoundError(f"Folder not found: {folder}")
        exts = {".jpg",".jpeg",".png",".bmp",".webp",".tiff"}
        if recursive:
            files = [f for f in folder_p.rglob("*") if f.suffix.lower() in exts]
        else:
            files = [f for f in folder_p.glob("*") if f.suffix.lower() in exts]
        self.images_dir.mkdir(parents=True, exist_ok=True)
        imported = 0
        for f in files:
            dest = self.images_dir / f.name
            # avoid name collision by adding counter if exists
            if dest.exists() and dest.resolve() != f.resolve():
                base = f.stem
                ext = f.suffix
                i = 1
                while (self.images_dir / f"{base}_{i}{ext}").exists():
                    i+=1
                dest = self.images_dir / f"{base}_{i}{ext}"
            if copy:
                try:
                    shutil.copy2(str(f), str(dest))
                    path_to_store = str(dest)
                except Exception as e:
                    logger.warning(f"Copy failed {f}: {e}")
                    path_to_store = str(f)
            else:
                path_to_store = str(f)
            if path_to_store in self.images:
                continue
            img = cv2.imread(str(f))
            h,w = img.shape[:2] if img is not None else (0,0)
            ann = ImageAnnotations(image_path=path_to_store, image_id=f.stem, width=w, height=h)
            self.images[path_to_store] = ImageInfo(path=path_to_store, width=w, height=h, annotations=ann)
            imported+=1
        logger.info(f"Imported {imported} images from {folder}")
        return imported

    def import_video(self, video_path: str, fps: float = 1.0, extract_dir: str = None) -> int:
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
            if idx % step == 0:
                out_path = out_dir / f"{Path(video_path).stem}_{saved:06d}.jpg"
                cv2.imwrite(str(out_path), frame)
                h,w = frame.shape[:2]
                ann = ImageAnnotations(image_path=str(out_path), image_id=out_path.stem, width=w, height=h)
                self.images[str(out_path)] = ImageInfo(path=str(out_path), width=w, height=h, annotations=ann)
                saved+=1
            idx+=1
        cap.release()
        return saved

    def _try_load_yolo_labels(self):
        """If labels/*.txt exist, try to load"""
        if not self.labels_dir.exists():
            return
        for txt in self.labels_dir.glob("*.txt"):
            stem = txt.stem
            # find corresponding image with same stem
            img_path = None
            for impath in self.images.keys():
                if Path(impath).stem == stem:
                    img_path = impath
                    break
            if not img_path:
                continue
            info = self.images[img_path]
            # parse YOLO
            try:
                lines = txt.read_text().strip().splitlines()
                for line in lines:
                    if not line.strip():
                        continue
                    parts = line.split()
                    if len(parts) < 5:
                        continue
                    cid = int(parts[0])
                    cx,cy,bw,bh = map(float, parts[1:5])
                    w,h = info.width, info.height
                    x1 = (cx - bw/2)*w
                    y1 = (cy - bh/2)*h
                    x2 = (cx + bw/2)*w
                    y2 = (cy + bh/2)*h
                    cname = self.classes[cid] if cid < len(self.classes) else str(cid)
                    if not self.is_wanted(cid, cname):
                        continue
                    obj = AnnotationObject(
                        class_id=cid,
                        class_name=cname,
                        bbox_xyxy=(x1,y1,x2,y2),
                        bbox_xywh_norm=(cx,cy,bw,bh),
                        confidence=1.0,
                        is_ai=False,
                        area=(x2-x1)*(y2-y1)
                    )
                    info.annotations.objects.append(obj)
            except Exception as e:
                logger.warning(f"Failed to load label {txt}: {e}")

    def save(self):
        data = {
            "name": self.project_path.name,
            "classes": self.classes,
            "colors": self.colors,
            "wanted_classes": list(self.wanted_classes),
            "images_dir": str(self.images_dir),
            "labels_dir": str(self.labels_dir),
            "version": "2.0.0",
            "saved_at": time.time(),
        }
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(yaml.safe_dump(data, allow_unicode=True))
        # backup
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            backup_file = self.backup_dir / f"project_{int(time.time())}.yaml"
            backup_file.write_text(yaml.safe_dump(data))
            # keep only last 20 backups
            backups = sorted(self.backup_dir.glob("project_*.yaml"), key=lambda x: x.stat().st_mtime, reverse=True)
            for old in backups[20:]:
                old.unlink()
        except Exception as e:
            logger.warning(f"Backup failed: {e}")

    def get_image_list(self) -> List[ImageInfo]:
        return list(self.images.values())

    def get_filtered_images(self, wanted_classes: Optional[List[str]] = None) -> List[ImageInfo]:
        if wanted_classes:
            self.set_wanted_classes(wanted_classes)
        if not self.wanted_classes and not self.wanted_class_ids:
            return self.get_image_list()
        # return images that have at least one wanted object, or all images if we want to filter on import?
        # For batch processing, we return all images, filtering happens on objects
        return self.get_image_list()

    def remove_unwanted_objects(self):
        """Remove objects not in wanted_classes from all images"""
        if not self.wanted_classes and not self.wanted_class_ids:
            return
        for info in self.images.values():
            info.annotations.objects = self.filter_objects_by_wanted(info.annotations.objects)

    def add_class(self, name: str):
        if name not in self.classes:
            self.classes.append(name)
            self.save()

    def rename_class(self, old_name: str, new_name: str):
        if old_name not in self.classes:
            return
        idx = self.classes.index(old_name)
        self.classes[idx] = new_name
        # update objects
        for info in self.images.values():
            for obj in info.annotations.objects:
                if obj.class_name == old_name:
                    obj.class_name = new_name
                    obj.class_id = idx
                elif obj.class_id == idx:
                    obj.class_name = new_name
        self.save()

    def merge_classes(self, source_names: List[str], target_name: str):
        if target_name not in self.classes:
            self.classes.append(target_name)
        target_id = self.classes.index(target_name)
        source_ids = [self.classes.index(n) for n in source_names if n in self.classes]
        for info in self.images.values():
            for obj in info.annotations.objects:
                if obj.class_name in source_names or obj.class_id in source_ids:
                    obj.class_name = target_name
                    obj.class_id = target_id
        # optionally remove old class names? Keep but could remove
        self.save()
