from __future__ import annotations
from pathlib import Path
from typing import Dict, List
import xml.etree.ElementTree as ET
import cv2
from ..core.annotation import ImageInfo, ImageAnnotations, AnnotationObject

class VOCImporter:
    def import_folder(self, xml_dir: str, images_dir: str = None) -> Dict[str, ImageInfo]:
        xml_dir = Path(xml_dir)
        result = {}
        for xml_file in xml_dir.glob("*.xml"):
            try:
                tree = ET.parse(str(xml_file))
                root = tree.getroot()
                filename = root.findtext("filename","")
                size_node = root.find("size")
                w = int(size_node.findtext("width","0")) if size_node is not None else 0
                h = int(size_node.findtext("height","0")) if size_node is not None else 0
                img_path = Path(images_dir)/filename if images_dir else Path(filename)
                if not img_path.exists():
                    # try same folder as xml
                    img_path = xml_dir / filename
                if img_path.exists() and (w==0 or h==0):
                    cv_img = cv2.imread(str(img_path))
                    if cv_img is not None:
                        h,w = cv_img.shape[:2]
                ann = ImageAnnotations(image_path=str(img_path), image_id=xml_file.stem, width=w, height=h)
                for obj_node in root.findall("object"):
                    cname = obj_node.findtext("name","object")
                    bnd = obj_node.find("bndbox")
                    if bnd is None:
                        continue
                    x1 = float(bnd.findtext("xmin","0"))
                    y1 = float(bnd.findtext("ymin","0"))
                    x2 = float(bnd.findtext("xmax","0"))
                    y2 = float(bnd.findtext("ymax","0"))
                    cx = ((x1+x2)/2)/w if w else 0
                    cy = ((y1+y2)/2)/h if h else 0
                    bw = (x2-x1)/w if w else 0
                    bh = (y2-y1)/h if h else 0
                    obj = AnnotationObject(class_id=0, class_name=cname, bbox_xyxy=(x1,y1,x2,y2), bbox_xywh_norm=(cx,cy,bw,bh))
                    ann.objects.append(obj)
                result[str(img_path)] = ImageInfo(path=str(img_path), width=w, height=h, annotations=ann)
            except Exception as e:
                print(f"VOC import error {xml_file}: {e}")
        return result
