#pragma once
#include "idetector.h"

namespace yolo {

class OnnxDetector : public IDetector {
public:
    OnnxDetector(const std::string& model_path,
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
    std::string model_name() const override { return model_name_; }
    ~OnnxDetector();

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
    std::string model_path_;
    std::string device_;
    int imgsz_;
    bool half_;
    std::vector<std::string> class_names_;
    std::string model_name_;
    float ratio_{1.f};
    cv::Point2f dwdh_{0,0};
    cv::Size orig_{0,0};
};

}
