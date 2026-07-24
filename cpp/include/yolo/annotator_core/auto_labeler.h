#pragma once
#include "annotation.h"
#include "yolo/detector/idetector.h"
#include <string>
#include <vector>
#include <memory>

namespace yolo {
namespace annotator {

class AutoLabeler {
public:
    AutoLabeler(const std::string& model_path, const std::string& device="cpu", float conf=0.3f, float iou=0.45f);
    bool load();
    std::vector<AnnotationObject> detect_image(const std::string& image_path);
    std::vector<AnnotationObject> detect_mat(const cv::Mat& img);

private:
    std::string model_path_;
    std::string device_;
    float conf_thres_;
    float iou_thres_;
    std::unique_ptr<IDetector> detector_;
};

}
}
