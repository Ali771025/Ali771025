#include "yolo/annotator_core/auto_labeler.h"
#include "yolo/detector/detector_factory.h"
#include <opencv2/imgcodecs.hpp>
#include <spdlog/spdlog.h>

namespace yolo {
namespace annotator {

AutoLabeler::AutoLabeler(const std::string& model_path, const std::string& device, float conf, float iou)
    : model_path_(model_path), device_(device), conf_thres_(conf), iou_thres_(iou) {}

bool AutoLabeler::load() {
    detector_ = create_detector(model_path_, "auto", device_, 640, conf_thres_, iou_thres_, 300);
    if (!detector_->load()) { spdlog::error("AutoLabeler load failed {}", model_path_); return false; }
    detector_->warmup(5);
    return true;
}

std::vector<AnnotationObject> AutoLabeler::detect_image(const std::string& image_path) {
    cv::Mat img = cv::imread(image_path);
    if (img.empty()) return {};
    return detect_mat(img);
}

std::vector<AnnotationObject> AutoLabeler::detect_mat(const cv::Mat& img) {
    std::vector<AnnotationObject> out;
    if (!detector_) return out;
    FrameResult res = detector_->detect(img, 0);
    for(auto& det: res.detections) {
        AnnotationObject obj;
        obj.id = std::to_string(rand());
        obj.class_id = det.class_id;
        obj.class_name = det.class_name;
        obj.xyxy = {det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2};
        obj.confidence = det.confidence;
        obj.is_ai = true;
        obj.area = det.area;
        // norm
        obj.xywh_norm = {det.xywh_norm[0], det.xywh_norm[1], det.xywh_norm[2], det.xywh_norm[3]};
        out.push_back(obj);
    }
    return out;
}

}
}
