#include "yolo/detector/opencv_dnn_detector.h"
#include "yolo/core/detection.h"
#include <opencv2/imgproc.hpp>
#include <opencv2/dnn.hpp>
#include <spdlog/spdlog.h>
#include <fstream>
#include <chrono>

namespace yolo {

static std::vector<std::string> COCO = {"person","bicycle","car","motorcycle","airplane","bus","train","truck","boat","traffic light","fire hydrant","stop sign","parking meter","bench","bird","cat","dog","horse","sheep","cow","elephant","bear","zebra","giraffe","backpack","umbrella","handbag","tie","suitcase","frisbee","skis","snowboard","sports ball","kite","baseball bat","baseball glove","skateboard","surfboard","tennis racket","bottle","wine glass","cup","fork","knife","spoon","bowl","banana","apple","sandwich","orange","broccoli","carrot","hot dog","pizza","donut","cake","chair","couch","potted plant","bed","dining table","toilet","tv","laptop","mouse","remote","keyboard","cell phone","microwave","oven","toaster","sink","refrigerator","book","clock","vase","scissors","teddy bear","hair drier","toothbrush"};

OpenCVDNNDetector::OpenCVDNNDetector(const std::string& model_path, const std::string& device, int imgsz, float conf, float iou, int max_det, const std::vector<int>& classes, bool half)
    : model_path_(model_path), device_(device), imgsz_(imgsz), half_(half) {
    conf_thres = conf;
    iou_thres = iou;
    max_det = max_det;
    class_filter = classes;
}

bool OpenCVDNNDetector::load() {
    try {
        spdlog::info("Loading OpenCV DNN model: {}", model_path_);
        net_ = cv::dnn::readNet(model_path_);
        if (device_=="cuda" || device_.rfind("cuda",0)==0) {
            try {
                net_.setPreferableBackend(cv::dnn::DNN_BACKEND_CUDA);
                net_.setPreferableTarget(cv::dnn::DNN_TARGET_CUDA_FP16);
            } catch (...) {
                net_.setPreferableBackend(cv::dnn::DNN_BACKEND_OPENCV);
                net_.setPreferableTarget(cv::dnn::DNN_TARGET_CPU);
            }
        } else {
            net_.setPreferableBackend(cv::dnn::DNN_BACKEND_OPENCV);
            net_.setPreferableTarget(cv::dnn::DNN_TARGET_CPU);
        }
        class_names_ = COCO;
        // try yaml companion
        std::string yaml_path = model_path_;
        auto dot = yaml_path.find_last_of('.');
        if (dot!=std::string::npos) yaml_path = yaml_path.substr(0,dot)+".yaml";
        std::ifstream f(yaml_path);
        if (f.good()) {
            // naive parse for names
            // ignore for now
        }
        model_name_str_ = model_path_;
        return true;
    } catch (const std::exception& e) {
        spdlog::error("Failed to load DNN model {}: {}", model_path_, e.what());
        return false;
    }
}

void OpenCVDNNDetector::warmup(int iters) {
    cv::Mat dummy(imgsz_, imgsz_, CV_8UC3, cv::Scalar(0,0,0));
    for(int i=0;i<iters;i++) detect(dummy,i);
}

cv::Mat OpenCVDNNDetector::preprocess(const cv::Mat& frame, float& ratio, cv::Point2f& dwdh, cv::Size& orig) {
    int h = frame.rows, w = frame.cols;
    orig = cv::Size(w,h);
    ratio = std::min((float)imgsz_/h, (float)imgsz_/w);
    int new_w = int(std::round(w*ratio));
    int new_h = int(std::round(h*ratio));
    cv::Mat resized;
    cv::resize(frame, resized, cv::Size(new_w,new_h));
    int dw = imgsz_ - new_w;
    int dh = imgsz_ - new_h;
    float dw_f = dw/2.0f, dh_f = dh/2.0f;
    dwdh = cv::Point2f(dw_f, dh_f);
    cv::Mat out;
    cv::copyMakeBorder(resized, out, int(std::round(dh_f-0.1f)), int(std::round(dh_f+0.1f)), int(std::round(dw_f-0.1f)), int(std::round(dw_f+0.1f)), cv::BORDER_CONSTANT, cv::Scalar(114,114,114));
    return out;
}

std::vector<Detection> OpenCVDNNDetector::postprocess(const std::vector<cv::Mat>& outputs, float ratio, cv::Point2f dwdh, cv::Size orig, int frame_id, double inf_ms) {
    std::vector<Detection> dets;
    if (outputs.empty()) return dets;
    cv::Mat pred = outputs[0];
    // Determine layout
    // YOLOv8: (1,84,8400) or (1,8400,84)
    // We'll convert to vector of rows
    int dims = pred.dims;
    std::vector<int> shape;
    for(int i=0;i<dims;i++) shape.push_back(pred.size[i]);
    cv::Mat output_mat;
    if (shape.size()==3) {
        // shape [1,84,8400] -> transpose
        int n = shape[1];
        int m = shape[2];
        if (n < m) {
            // n=84,m=8400 -> transpose to 8400x84
            cv::Mat transposed;
            // reshape: we have 1x84x8400 flattened: need manual
            // Use Reshape and transpose via cv::transpose after reshaping?
            // pred is 1x84x8400 as Mat continuous: let's convert to 84x8400 then transpose
            cv::Mat tmp = pred.reshape(1, n); // 84 rows, 8400 cols?
            // Actually pred.reshape reshapes to 1 channel? simplistically use for loop?
            // For simplicity, we convert using vector iteration and produce matrix 8400x84
            std::vector<float> data;
            data.assign((float*)pred.data, (float*)pred.data + n*m);
            cv::Mat mat_n_m(n,m,CV_32F, data.data());
            cv::Mat mat_m_n;
            cv::transpose(mat_n_m, mat_m_n);
            output_mat = mat_m_n.clone(); // 8400x84
        } else {
            // already 1x8400x84
            output_mat = pred.reshape(1, m).clone();
        }
    } else if (shape.size()==2) {
        output_mat = pred.clone();
    } else {
        // try to infer
        output_mat = pred.reshape(1, pred.total()/84).clone(); // fallback
    }

    // output_mat rows = num_boxes, cols = 84
    if (output_mat.cols < 5) return dets;
    int num_classes = output_mat.cols - 4;

    std::vector<cv::Rect> boxes;
    std::vector<float> scores;
    std::vector<int> class_ids;

    for(int i=0;i<output_mat.rows;i++) {
        float* row = output_mat.ptr<float>(i);
        float cx = row[0], cy = row[1], w = row[2], h = row[3];
        float* class_scores = row+4;
        // find max class
        int max_id = 0;
        float max_score = class_scores[0];
        for(int c=1;c<num_classes;c++) {
            if (class_scores[c] > max_score) { max_score = class_scores[c]; max_id=c; }
        }
        if (max_score < conf_thres) continue;
        if (!class_filter.empty() && std::find(class_filter.begin(), class_filter.end(), max_id)==class_filter.end()) continue;

        float x1 = cx - w/2;
        float y1 = cy - h/2;
        float x2 = cx + w/2;
        float y2 = cy + h/2;
        // scale back
        x1 = (x1 - dwdh.x)/ratio;
        y1 = (y1 - dwdh.y)/ratio;
        x2 = (x2 - dwdh.x)/ratio;
        y2 = (y2 - dwdh.y)/ratio;

        BBox b;
        b.x1=x1; b.y1=y1; b.x2=x2; b.y2=y2;
        BBox clipped = clip_bbox(b, orig.width, orig.height);
        if (clipped.w()<=0 || clipped.h()<=0) continue;
        boxes.emplace_back(cv::Rect(cv::Point(int(clipped.x1), int(clipped.y1)), cv::Point(int(clipped.x2), int(clipped.y2))));
        scores.push_back(max_score);
        class_ids.push_back(max_id);
    }

    std::vector<int> indices;
    cv::dnn::NMSBoxes(boxes, scores, conf_thres, iou_thres, indices);
    // limit max_det
    if ((int)indices.size() > max_det) {
        // sort by score descending
        std::sort(indices.begin(), indices.end(), [&](int a, int b){return scores[a] > scores[b];});
        indices.resize(max_det);
    }

    for(int idx: indices) {
        Detection det;
        det.class_id = class_ids[idx];
        det.class_name = (det.class_id >=0 && det.class_id < (int)class_names_.size()) ? class_names_[det.class_id] : std::to_string(det.class_id);
        det.confidence = scores[idx];
        det.bbox.x1 = boxes[idx].x;
        det.bbox.y1 = boxes[idx].y;
        det.bbox.x2 = boxes[idx].x + boxes[idx].width;
        det.bbox.y2 = boxes[idx].y + boxes[idx].height;
        compute_derived(det, orig.width, orig.height);
        det.frame_id = frame_id;
        det.model_name = model_name_str_;
        det.inference_time_ms = inf_ms;
        det.timestamp_unix = std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
        dets.push_back(det);
    }
    return dets;
}

FrameResult OpenCVDNNDetector::detect(const cv::Mat& frame, int frame_id) {
    if (net_.empty()) {
        if (!load()) {
            return FrameResult{frame_id, frame.cols, frame.rows, {}, 0, 0};
        }
    }
    float ratio; cv::Point2f dwdh; cv::Size orig;
    cv::Mat letter = preprocess(frame, ratio, dwdh, orig);
    cv::Mat blob = cv::dnn::blobFromImage(letter, 1/255.0, cv::Size(imgsz_, imgsz_), cv::Scalar(), true, false);
    net_.setInput(blob);
    auto t0 = std::chrono::high_resolution_clock::now();
    std::vector<cv::Mat> outs;
    try {
        net_.forward(outs, net_.getUnconnectedOutLayersNames());
    } catch (const std::exception& e) {
        spdlog::error("DNN forward failed: {}", e.what());
        return FrameResult{frame_id, orig.width, orig.height, {}, 0, 0};
    }
    auto t1 = std::chrono::high_resolution_clock::now();
    double inf_ms = std::chrono::duration<double, std::milli>(t1-t0).count();
    auto dets = postprocess(outs, ratio, dwdh, orig, frame_id, inf_ms);
    FrameResult res;
    res.frame_id = frame_id;
    res.width = orig.width;
    res.height = orig.height;
    res.detections = std::move(dets);
    res.inference_time_ms = inf_ms;
    res.timestamp_unix = std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
    return res;
}

}
