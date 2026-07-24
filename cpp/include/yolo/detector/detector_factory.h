#pragma once
#include "idetector.h"
#include <memory>
#include <string>

namespace yolo {

std::unique_ptr<IDetector> create_detector(const std::string& model_path,
                                           const std::string& backend="auto",
                                           const std::string& device="auto",
                                           int imgsz=640,
                                           float conf=0.35f,
                                           float iou=0.45f,
                                           int max_det=300,
                                           const std::vector<int>& classes={},
                                           bool half=false);

}
