import sys
sys.path.insert(0, ".")
from pro_annotator.core.annotation import AnnotationObject
from pro_annotator.core.validators import LabelValidator
from pro_annotator.core.dataset import DatasetManager
from pro_annotator.ai.llm_analyzer import LLMAnalyzer

def test_iou():
    a = AnnotationObject(bbox_xyxy=(0,0,10,10))
    b = AnnotationObject(bbox_xyxy=(0,0,10,10))
    assert abs(AnnotationObject.iou(a,b) - 1.0) < 1e-5
    c = AnnotationObject(bbox_xyxy=(20,20,30,30))
    assert AnnotationObject.iou(a,c) == 0.0

def test_validator_tiny():
    v = LabelValidator(min_box_size=10)
    from pro_annotator.core.annotation import ImageAnnotations
    ann = ImageAnnotations(image_path="test.jpg", width=100, height=100)
    ann.objects.append(AnnotationObject(class_id=0, class_name="person", bbox_xyxy=(0,0,2,2)))
    issues = v.validate_image(ann)
    assert any(i.type=="tiny" for i in issues)

def test_validator_duplicate():
    v = LabelValidator()
    from pro_annotator.core.annotation import ImageAnnotations
    ann = ImageAnnotations(image_path="test.jpg", width=100, height=100)
    ann.objects.append(AnnotationObject(class_id=0, class_name="person", bbox_xyxy=(0,0,10,10)))
    ann.objects.append(AnnotationObject(class_id=0, class_name="person", bbox_xyxy=(0,0,10,10)))
    issues = v.validate_image(ann)
    assert any(i.type=="duplicate" for i in issues)

def test_dataset_stats():
    from pro_annotator.core.annotation import ImageInfo, ImageAnnotations
    img1 = ImageInfo(path="img1.jpg", width=100, height=100, annotations=ImageAnnotations(image_path="img1.jpg", width=100, height=100))
    img1.annotations.objects.append(AnnotationObject(class_name="car", bbox_xyxy=(0,0,10,10)))
    img2 = ImageInfo(path="img2.jpg", width=100, height=100, annotations=ImageAnnotations(image_path="img2.jpg", width=100, height=100))
    img2.annotations.objects.append(AnnotationObject(class_name="person", bbox_xyxy=(0,0,10,10)))
    mgr = DatasetManager(["person","car"])
    stats = mgr.compute_stats([img1, img2])
    assert stats["total_images"]==2
    assert stats["class_distribution"]["car"]==1

def test_llm_dummy():
    analyzer = LLMAnalyzer(model_path=None, backend="dummy")
    analyzer.load()
    from pro_annotator.core.annotation import ImageAnnotations
    ann = ImageAnnotations(image_path="img.jpg", width=100, height=100)
    ann.objects.append(AnnotationObject(class_name="car", bbox_xyxy=(0,0,10,10), confidence=0.9, is_ai=True))
    result = analyzer.analyze_image_labels(ann)
    assert result.qa_score >=0
    assert "car" in result.description or "1" in result.description

def test_wanted_filter():
    from pro_annotator.core.project import AnnotationProject
    proj = AnnotationProject.create("/tmp/test_proj_filter", classes=["person","car","dog"])
    proj.set_wanted_classes(["person","car"])
    assert proj.is_wanted(0, "person") == True
    assert proj.is_wanted(2, "dog") == False
    # cleanup
    import shutil
    shutil.rmtree("/tmp/test_proj_filter", ignore_errors=True)
