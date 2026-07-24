#pragma once
#include <string>
#include <vector>
#include <tuple>
#include <array>

namespace yolo {

struct BBox {
    float x1{0}, y1{0}, x2{0}, y2{0};
    float x() const { return x1; }
    float y() const { return y1; }
    float w() const { return x2 - x1; }
    float h() const { return y2 - y1; }
    float cx() const { return (x1+x2)*0.5f; }
    float cy() const { return (y1+y2)*0.5f; }
    float area() const { float ww = w(); float hh = h(); return ww*hh >0 ? ww*hh : 0; }
    float aspect_ratio() const { float hh = h(); return hh>1e-6 ? w()/hh : 0; }
};

struct Detection {
    int class_id{-1};
    std::string class_name;
    float confidence{0.f};
    BBox bbox;
    // derived
    std::array<float,4> xywh{0,0,0,0}; // x,y,w,h
    std::array<float,4> xywh_norm{0,0,0,0}; // cx,cy,w,h norm 0-1
    std::array<float,2> center{0,0};
    float area{0};
    float aspect_ratio{0};
    int track_id{-1};
    int frame_id{0};
    std::string model_name;
    double inference_time_ms{0};
    double timestamp_unix{0};
};

struct FrameResult {
    int frame_id{0};
    int width{0};
    int height{0};
    std::vector<Detection> detections;
    double inference_time_ms{0};
    double timestamp_unix{0};
};

// utilities
inline void compute_derived(Detection& det, int img_w, int img_h) {
    det.xywh = {det.bbox.x1, det.bbox.y1, det.bbox.w(), det.bbox.h()};
    if (img_w >0 && img_h>0) {
        det.xywh_norm = {det.bbox.cx()/img_w, det.bbox.cy()/img_h, det.bbox.w()/img_w, det.bbox.h()/img_h};
    }
    det.center = {det.bbox.cx(), det.bbox.cy()};
    det.area = det.bbox.area();
    det.aspect_ratio = det.bbox.aspect_ratio();
}

inline BBox clip_bbox(const BBox& b, int w, int h) {
    BBox out;
    out.x1 = std::max(0.f, std::min(b.x1, (float)(w-1)));
    out.y1 = std::max(0.f, std::min(b.y1, (float)(h-1)));
    out.x2 = std::max(0.f, std::min(b.x2, (float)(w-1)));
    out.y2 = std::max(0.f, std::min(b.y2, (float)(h-1)));
    if (out.x2 < out.x1) std::swap(out.x1, out.x2);
    if (out.y2 < out.y1) std::swap(out.y1, out.y2);
    return out;
}

inline float iou(const BBox& a, const BBox& b) {
    float x1 = std::max(a.x1, b.x1);
    float y1 = std::max(a.y1, b.y1);
    float x2 = std::min(a.x2, b.x2);
    float y2 = std::min(a.y2, b.y2);
    if (x2 <= x1 || y2 <= y1) return 0.f;
    float inter = (x2-x1)*(y2-y1);
    float ua = a.area() + b.area() - inter;
    if (ua <=0) return 0.f;
    return inter/ua;
}

}
