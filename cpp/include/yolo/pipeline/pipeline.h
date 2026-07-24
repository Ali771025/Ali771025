#include <opencv2/core.hpp>
#include <opencv2/videoio.hpp>
#pragma once
#include "yolo/core/config.h"
#include "yolo/core/detection.h"
#include "yolo/detector/idetector.h"
#include "yolo/source/isource.h"
#include "bounded_queue.h"
#include "yolo/logging/log_writer.h"
#include <thread>
#include <atomic>
#include <memory>

namespace yolo {

struct FramePacket {
    int frame_id{0};
    cv::Mat frame;
    double timestamp_capture{0};
    std::string source_status{"ok"};
};

struct InferencePacket {
    FramePacket frame_packet;
    FrameResult result;
    double timestamp_done{0};
};

class DetectionPipeline {
public:
    DetectionPipeline(const AppConfig& config);
    ~DetectionPipeline();

    bool start();
    void stop();

    bool get_latest(InferencePacket& out, int timeout_ms=100);
    bool is_stopped() const { return stop_flag_.load(); }
    std::string source_status() const { return source_status_; }
    int dropped_frames() const { return dropped_frames_; }

    // fps/latency
    double fps() const { return fps_; }
    double inf_fps() const { return inf_fps_; }
    double avg_latency_ms() const { return avg_latency_; }

    std::unique_ptr<IDetector>& detector() { return detector_; }
    std::unique_ptr<ISource>& source() { return source_; }

    AppConfig config;

private:
    std::unique_ptr<ISource> source_;
    std::unique_ptr<IDetector> detector_;
    std::unique_ptr<LogWriter> logger_;

    BoundedQueue<FramePacket> capture_queue_;
    BoundedQueue<InferencePacket> inference_queue_;
    BoundedQueue<InferencePacket> render_queue_;

    std::thread capture_thread_;
    std::thread inference_thread_;
    std::thread render_thread_;

    std::atomic<bool> stop_flag_{false};
    std::atomic<bool> pause_flag_{false};

    void capture_loop();
    void inference_loop();
    void render_loop();

    bool open_source_with_retry();

    std::string source_status_{"init"};
    int dropped_frames_{0};
    double fps_{0}, inf_fps_{0}, avg_latency_{0};
    int frame_counter_{0};
    cv::VideoWriter video_writer_;
};

}
