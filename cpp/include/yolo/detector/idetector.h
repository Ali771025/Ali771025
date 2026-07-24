#pragma once
#include "yolo/core/detection.h"
#include <opencv2/core.hpp>
#include <string>
#include <vector>

namespace yolo {

class IDetector {
public:
    virtual ~IDetector() = default;
    virtual bool load() = 0;
    virtual void warmup(int iters=10) = 0;
    virtual FrameResult detect(const cv::Mat& frame, int frame_id=0) = 0;
    virtual void shutdown() {}
    virtual std::vector<std::string> class_names() const = 0;
    virtual std::string model_name() const = 0;
    float conf_thres{0.35f};
    float iou_thres{0.45f};
    int max_det{300};
    std::vector<int> class_filter;
};

}
