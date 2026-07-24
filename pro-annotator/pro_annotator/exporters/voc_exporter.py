from __future__ import annotations
from pathlib import Path
from typing import List
import xml.etree.ElementTree as ET
from xml.dom import minidom
from ..core.annotation import ImageInfo

class VOCExporter:
    def __init__(self, classes: List[str]):
        self.classes = classes

    def export(self, images: List[ImageInfo], output_dir: str):
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for img_info in images:
            annotation = ET.Element("annotation")
            folder = ET.SubElement(annotation, "folder")
            folder.text = str(Path(img_info.path).parent.name)
            filename = ET.SubElement(annotation, "filename")
            filename.text = Path(img_info.path).name
            size = ET.SubElement(annotation, "size")
            w = ET.SubElement(size, "width"); w.text = str(img_info.width)
            h = ET.SubElement(size, "height"); h.text = str(img_info.height)
            d = ET.SubElement(size, "depth"); d.text = "3"
            for obj in img_info.annotations.objects:
                if not obj.visible:
                    continue
                obj_el = ET.SubElement(annotation, "object")
                name = ET.SubElement(obj_el, "name"); name.text = obj.class_name
                pose = ET.SubElement(obj_el, "pose"); pose.text = "Unspecified"
                trunc = ET.SubElement(obj_el, "truncated"); trunc.text = "0"
                diff = ET.SubElement(obj_el, "difficult"); diff.text = "0"
                bndbox = ET.SubElement(obj_el, "bndbox")
                x1,y1,x2,y2 = map(int, obj.bbox_xyxy)
                xmin = ET.SubElement(bndbox, "xmin"); xmin.text = str(x1)
                ymin = ET.SubElement(bndbox, "ymin"); ymin.text = str(y1)
                xmax = ET.SubElement(bndbox, "xmax"); xmax.text = str(x2)
                ymax = ET.SubElement(bndbox, "ymax"); ymax.text = str(y2)
            xml_str = ET.tostring(annotation, encoding="utf-8")
            pretty = minidom.parseString(xml_str).toprettyxml(indent="  ")
            out_file = out_dir / f"{Path(img_info.path).stem}.xml"
            out_file.write_text(pretty, encoding="utf-8")
        return out_dir
