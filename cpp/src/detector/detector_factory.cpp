#include "yolo/detector/detector_factory.h"
#include "yolo/detector/opencv_dnn_detector.h"
#include "yolo/detector/onnx_detector.h"
#include <algorithm>

namespace yolo {

std::unique_ptr<IDetector> create_detector(const std::string& model_path, const std::string& backend, const std::string& device, int imgsz, float conf, float iou, int max_det, const std::vector<int>& classes, bool half) {
    std::string b = backend;
    std::transform(b.begin(), b.end(), b.begin(), ::tolower);
    std::string lower_path = model_path;
    std::transform(lower_path.begin(), lower_path.end(), lower_path.begin(), ::tolower);

    if (b=="auto") {
        if (lower_path.rfind(".pt")==lower_path.size()-3) b="opencv";
        else if (lower_path.rfind(".engine")!=std::string::npos || lower_path.rfind(".trt")!=std::string::npos) b="tensorrt";
        else b="onnx";
    }

    if (b=="onnx") {
        return std::make_unique<OnnxDetector>(model_path, device, imgsz, conf, iou, max_det, classes, half);
    } else if (b=="opencv" || b=="dnn") {
        return std::make_unique<OpenCVDNNDetector>(model_path, device, imgsz, conf, iou, max_det, classes, half);
    } else if (b=="tensorrt") {
        // fallback to ONNX for now
        return std::make_unique<OnnxDetector>(model_path, device, imgsz, conf, iou, max_det, classes, half);
    } else {
        return std::make_unique<OpenCVDNNDetector>(model_path, device, imgsz, conf, iou, max_det, classes, half);
    }
}

}
