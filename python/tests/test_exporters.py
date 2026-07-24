import sys, tempfile
from pathlib import Path
sys.path.insert(0, "python")
from yolo_annotator.core.annotation import ImageInfo, ImageAnnotations, AnnotationObject
from yolo_annotator.exporters import YOLOExporter, COCOExporter, VOCExporter

def make_dummy():
    ann=ImageAnnotations(image_path="img.jpg", image_id="img", width=640, height=480)
    obj=AnnotationObject(class_id=0, class_name="person", bbox_xyxy=(10,20,100,200), bbox_xywh_norm=(0.08,0.22,0.14,0.37))
    ann.objects.append(obj)
    info=ImageInfo(path="img.jpg", width=640, height=480, annotations=ann)
    return [info]

def test_yolo_export():
    infos=make_dummy()
    with tempfile.TemporaryDirectory() as tmp:
        exp=YOLOExporter(tmp, ["person"])
        out=exp.export(infos, output_dir=tmp)
        assert (Path(tmp)/"labels"/"img.txt").exists()

def test_coco_export():
    infos=make_dummy()
    with tempfile.TemporaryDirectory() as tmp:
        exp=COCOExporter(["person"])
        out=exp.export(infos, str(Path(tmp)/"coco.json"))
        assert Path(out).exists()

def test_voc_export():
    infos=make_dummy()
    with tempfile.TemporaryDirectory() as tmp:
        exp=VOCExporter(["person"])
        out=exp.export(infos, tmp)
        assert (Path(tmp)/"img.xml").exists()
