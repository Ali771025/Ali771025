#pragma once
#include <string>
#include <vector>
#include <array>

namespace yolo {
namespace annotator {

struct AnnotationObject {
    std::string id;
    int class_id{0};
    std::string class_name{"object"};
    std::array<float,4> xyxy{0,0,0,0};
    std::array<float,4> xywh_norm{0,0,0,0};
    float confidence{1.f};
    bool is_ai{false};
    bool is_reviewed{false};
    bool visible{true};
    float area{0};
};

struct ImageAnnotations {
    std::string image_path;
    std::string image_id;
    int width{0}, height{0};
    std::vector<AnnotationObject> objects;
    bool reviewed{false};
    std::string status{"not-reviewed"};
};

struct ImageInfo {
    std::string path;
    int width{0}, height{0};
    ImageAnnotations annotations;
};

}
}
