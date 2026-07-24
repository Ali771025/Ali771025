#include "yolo/detector/onnx_detector.h"
#include "yolo/detector/opencv_dnn_detector.h"
#include <spdlog/spdlog.h>

#ifdef YOLO_USE_ONNXRUNTIME
#include <onnxruntime_cxx_api.h>
#include <opencv2/imgproc.hpp>
#include <chrono>

namespace yolo {

struct OnnxDetector::Impl {
    Ort::Env env{ORT_LOGGING_LEVEL_WARNING, "yolo"};
    std::unique_ptr<Ort::Session> session;
    std::vector<std::string> input_names;
    std::vector<std::string> output_names;
    std::vector<const char*> input_names_c;
    std::vector<const char*> output_names_c;
    std::vector<std::vector<int64_t>> input_shapes;
    std::string model_path;
};

OnnxDetector::OnnxDetector(const std::string& model_path, const std::string& device, int imgsz, float conf, float iou, int max_det, const std::vector<int>& classes, bool half)
    : impl_(std::make_unique<Impl>()), model_path_(model_path), device_(device), imgsz_(imgsz), half_(half) {
    conf_thres=conf; iou_thres=iou; max_det=max_det; class_filter=classes;
    impl_->model_path=model_path;
}

OnnxDetector::~OnnxDetector() = default;

bool OnnxDetector::load() {
    try {
        spdlog::info("Loading ONNX Runtime model: {}", model_path_);
        Ort::SessionOptions opts;
        opts.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
        if (device_=="cuda" || device_.find("cuda")==0) {
            try {
                OrtCUDAProviderOptions cuda_opts;
                opts.AppendExecutionProvider_CUDA(cuda_opts);
            } catch (...) {
                spdlog::warn("CUDA provider not available, fallback to CPU");
            }
        }
        impl_->session = std::make_unique<Ort::Session>(impl_->env, model_path_.c_str(), opts);
        Ort::AllocatorWithDefaultOptions alloc;
        auto in_meta = impl_->session->GetInputTypeInfo().GetTensorTypeAndShapeInfo();
        // simplified provider listing
        size_t num_in = impl_->session->GetInputCount();
        for(size_t i=0;i<num_in;i++) {
            auto name = impl_->session->GetInputNameAllocated(i, alloc);
            impl_->input_names.emplace_back(name.get());
        }
        size_t num_out = impl_->session->GetOutputCount();
        for(size_t i=0;i<num_out;i++) {
            auto name = impl_->session->GetOutputNameAllocated(i, alloc);
            impl_->output_names.emplace_back(name.get());
        }
        impl_->input_names_c.clear();
        impl_->output_names_c.clear();
        for(auto& s: impl_->input_names) impl_->input_names_c.push_back(s.c_str());
        for(auto& s: impl_->output_names) impl_->output_names_c.push_back(s.c_str());

        class_names_ = {"person","bicycle","car","motorcycle","airplane","bus","train","truck","boat","traffic light","fire hydrant","stop sign","parking meter","bench","bird","cat","dog","horse","sheep","cow","elephant","bear","zebra","giraffe","backpack","umbrella","handbag","tie","suitcase","frisbee","skis","snowboard","sports ball","kite","baseball bat","baseball glove","skateboard","surfboard","tennis racket","bottle","wine glass","cup","fork","knife","spoon","bowl","banana","apple","sandwich","orange","broccoli","carrot","hot dog","pizza","donut","cake","chair","couch","potted plant","bed","dining table","toilet","tv","laptop","mouse","remote","keyboard","cell phone","microwave","oven","toaster","sink","refrigerator","book","clock","vase","scissors","teddy bear","hair drier","toothbrush"};
        model_name_ = model_path_;
        return true;
    } catch (const std::exception& e) {
        spdlog::error("ONNX load failed {}: {}", model_path_, e.what());
        return false;
    }
}

void OnnxDetector::warmup(int iters) {
    cv::Mat dummy(imgsz_, imgsz_, CV_8UC3, cv::Scalar(0,0,0));
    for(int i=0;i<iters;i++) detect(dummy,i);
}

FrameResult OnnxDetector::detect(const cv::Mat& frame, int frame_id) {
    if (!impl_->session) {
        if (!load()) return FrameResult{frame_id, frame.cols, frame.rows, {},0,0};
    }
    // preprocess letterbox
    int h=frame.rows, w=frame.cols;
    float ratio = std::min((float)imgsz_/h, (float)imgsz_/w);
    int new_w = int(std::round(w*ratio));
    int new_h = int(std::round(h*ratio));
    cv::Mat resized;
    cv::resize(frame, resized, cv::Size(new_w,new_h));
    int dw = imgsz_ - new_w;
    int dh = imgsz_ - new_h;
    float dw_f = dw/2.f, dh_f = dh/2.f;
    cv::Mat out;
    cv::copyMakeBorder(resized, out, int(std::round(dh_f-0.1f)), int(std::round(dh_f+0.1f)), int(std::round(dw_f-0.1f)), int(std::round(dw_f+0.1f)), cv::BORDER_CONSTANT, cv::Scalar(114,114,114));
    cv::Mat rgb;
    cv::cvtColor(out, rgb, cv::COLOR_BGR2RGB);
    rgb.convertTo(rgb, CV_32F, 1/255.0);
    // HWC to CHW
    std::vector<float> input_tensor(1*3*imgsz_*imgsz_);
    // fill
    for(int c=0;c<3;c++) {
        for(int y=0;y<imgsz_;y++) {
            for(int x=0;x<imgsz_;x++) {
                input_tensor[c*imgsz_*imgsz_ + y*imgsz_ + x] = rgb.at<cv::Vec3f>(y,x)[c];
            }
        }
    }
    Ort::MemoryInfo mem_info = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    std::array<int64_t,4> shape{1,3,imgsz_,imgsz_};
    Ort::Value input = Ort::Value::CreateTensor<float>(mem_info, input_tensor.data(), input_tensor.size(), shape.data(), 4);
    auto t0 = std::chrono::high_resolution_clock::now();
    std::vector<Ort::Value> outputs;
    try {
        outputs = impl_->session->Run(Ort::RunOptions{nullptr}, impl_->input_names_c.data(), &input, 1, impl_->output_names_c.data(), impl_->output_names_c.size());
    } catch (const std::exception& e) {
        spdlog::error("ONNX inference failed: {}", e.what());
        return FrameResult{frame_id, w, h, {},0,0};
    }
    auto t1 = std::chrono::high_resolution_clock::now();
    double inf_ms = std::chrono::duration<double, std::milli>(t1-t0).count();

    // parse output - assume first output is (1,84,8400) or (1,8400,84)
    float* out_data = outputs[0].GetTensorMutableData<float>();
    auto type_info = outputs[0].GetTensorTypeAndShapeInfo();
    auto out_shape = type_info.GetShape(); // e.g. {1,84,8400}
    std::vector<Detection> dets;
    if (out_shape.size()==3) {
        int d1 = (int)out_shape[1];
        int d2 = (int)out_shape[2];
        bool need_transpose = d1 < d2; // 84 vs 8400
        int num_boxes = need_transpose ? d2 : d1;
        int num_attrs = need_transpose ? d1 : d2;
        // create vector of boxes
        std::vector<cv::Rect> boxes;
        std::vector<float> scores;
        std::vector<int> class_ids;
        for(int i=0;i<num_boxes;i++) {
            float cx,cy,bw,bh;
            float max_score = -1;
            int max_id = -1;
            if (need_transpose) {
                // layout [1,84,8400] => data[ c*8400 + i ]
                cx = out_data[0*num_boxes + i];
                cy = out_data[1*num_boxes + i];
                bw = out_data[2*num_boxes + i];
                bh = out_data[3*num_boxes + i];
                for(int c=4;c<num_attrs;c++) {
                    float s = out_data[c*num_boxes + i];
                    if (s > max_score) { max_score=s; max_id=c-4; }
                }
            } else {
                // layout [1,8400,84]
                float* row = out_data + i*num_attrs;
                cx = row[0]; cy=row[1]; bw=row[2]; bh=row[3];
                for(int c=4;c<num_attrs;c++) {
                    float s=row[c];
                    if (s>max_score){max_score=s; max_id=c-4;}
                }
            }
            if (max_score < conf_thres) continue;
            if (!class_filter.empty() && std::find(class_filter.begin(), class_filter.end(), max_id)==class_filter.end()) continue;
            float x1 = cx - bw/2;
            float y1 = cy - bh/2;
            float x2 = cx + bw/2;
            float y2 = cy + bh/2;
            x1 = (x1 - dw_f)/ratio;
            y1 = (y1 - dh_f)/ratio;
            x2 = (x2 - dw_f)/ratio;
            y2 = (y2 - dh_f)/ratio;
            BBox b{x1,y1,x2,y2};
            BBox clip = clip_bbox(b,w,h);
            if (clip.w()<=0 || clip.h()<=0) continue;
            boxes.emplace_back(cv::Rect(cv::Point(int(clip.x1), int(clip.y1)), cv::Point(int(clip.x2), int(clip.y2))));
            scores.push_back(max_score);
            class_ids.push_back(max_id);
        }
        std::vector<int> indices;
        cv::dnn::NMSBoxes(boxes, scores, conf_thres, iou_thres, indices);
        if ((int)indices.size()>max_det) {
            std::sort(indices.begin(), indices.end(), [&](int a,int b){return scores[a]>scores[b];});
            indices.resize(max_det);
        }
        for(int idx: indices) {
            Detection det;
            det.class_id = class_ids[idx];
            det.class_name = (det.class_id>=0 && det.class_id < (int)class_names_.size()) ? class_names_[det.class_id] : std::to_string(det.class_id);
            det.confidence = scores[idx];
            det.bbox.x1 = boxes[idx].x; det.bbox.y1 = boxes[idx].y; det.bbox.x2 = boxes[idx].x+boxes[idx].width; det.bbox.y2 = boxes[idx].y+boxes[idx].height;
            compute_derived(det,w,h);
            det.frame_id=frame_id; det.model_name=model_name_; det.inference_time_ms=inf_ms;
            det.timestamp_unix = std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
            dets.push_back(det);
        }
    }

    FrameResult res;
    res.frame_id=frame_id; res.width=w; res.height=h; res.detections=std::move(dets); res.inference_time_ms=inf_ms;
    res.timestamp_unix = std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
    return res;
}

}

#else
// fallback to OpenCV DNN when ONNX Runtime not available
namespace yolo {

struct OnnxDetector::Impl {};

OnnxDetector::OnnxDetector(const std::string& model_path, const std::string& device, int imgsz, float conf, float iou, int max_det, const std::vector<int>& classes, bool half)
    : impl_(std::make_unique<Impl>()), model_path_(model_path), device_(device), imgsz_(imgsz), half_(half) {
    conf_thres=conf; iou_thres=iou; max_det=max_det; class_filter=classes;
}

OnnxDetector::~OnnxDetector() = default;
bool OnnxDetector::load() { spdlog::warn("ONNX Runtime not compiled, using OpenCV DNN fallback for {}", model_path_); return true; }
void OnnxDetector::warmup(int) {}
FrameResult OnnxDetector::detect(const cv::Mat& frame, int frame_id) {
    // delegate to OpenCV DNN detector
    static std::unique_ptr<OpenCVDNNDetector> fallback;
    if (!fallback) {
        fallback = std::make_unique<OpenCVDNNDetector>(model_path_, device_, imgsz_, conf_thres, iou_thres, max_det, class_filter, half_);
        fallback->load();
    }
    fallback->conf_thres = conf_thres;
    fallback->iou_thres = iou_thres;
    return fallback->detect(frame, frame_id);
}
std::vector<std::string> OnnxDetector::class_names() const { return {"person","bicycle","car"}; }
std::string OnnxDetector::model_name() const { return model_path_; }

}
#endif
