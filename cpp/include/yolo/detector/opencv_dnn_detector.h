#pragma once
#include "idetector.h"
#include <opencv2/dnn.hpp>

namespace yolo {

class OpenCVDNNDetector : public IDetector {
public:
    OpenCVDNNDetector(const std::string& model_path,
                      const std::string& device="cpu",
                      int imgsz=640,
                      float conf=0.35f,
                      float iou=0.45f,
                      int max_det=300,
                      const std::vector<int>& classes={},
                      bool half=false);
    bool load() override;
    void warmup(int iters=10) override;
    FrameResult detect(const cv::Mat& frame, int frame_id=0) override;
    std::vector<std::string> class_names() const override { return class_names_; }
    std::string model_name() const override { return model_path_; }

private:
    std::string model_path_;
    std::string device_;
    int imgsz_;
    bool half_;
    cv::dnn::Net net_;
    std::vector<std::string> class_names_;
    std::string model_name_str_;
    cv::Mat preprocess(const cv::Mat& frame, float& ratio, cv::Point2f& dwdh, cv::Size& orig);
    std::vector<Detection> postprocess(const std::vector<cv::Mat>& outputs, float ratio, cv::Point2f dwdh, cv::Size orig, int frame_id, double inf_ms);
};

}
