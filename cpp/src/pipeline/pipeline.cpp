#include "yolo/pipeline/pipeline.h"
#include "yolo/source/factory.h"
#include "yolo/detector/detector_factory.h"
#include "yolo/core/common.h"
#include <spdlog/spdlog.h>
#include <thread>
#include <chrono>

namespace yolo {

DetectionPipeline::DetectionPipeline(const AppConfig& config)
    : config(config),
      capture_queue_(config.pipeline.queue_size, config.pipeline.drop_policy),
      inference_queue_(config.pipeline.queue_size, config.pipeline.drop_policy),
      render_queue_(config.pipeline.queue_size, config.pipeline.drop_policy)
{
    std::string expanded = expand_source_with_secrets(config.source, config.secrets);
    std::string masked = mask_url(expanded);
    // copy for logging but need to update source string
    const_cast<AppConfig&>(this->config).source = expanded;
    source_ = create_source(expanded, config.source_type, config.pipeline.reconnect.timeout_ms);
    detector_ = create_detector(config.model.path, config.model.backend, config.device, config.imgsz, config.conf_thres, config.iou_thres, config.max_det, config.classes, config.half);
    if (config.output.log_path) {
        logger_ = std::make_unique<LogWriter>(*config.output.log_path, config.output.log_format, masked, config.source_type, config.model.path, config.device);
    }
}

DetectionPipeline::~DetectionPipeline() { stop(); }

bool DetectionPipeline::open_source_with_retry() {
    int retries=0;
    float delay = config.pipeline.reconnect.initial_delay;
    while(!stop_flag_.load()) {
        if (source_->open()) {
            source_status_="ok";
            spdlog::info("Source opened: {}", mask_url(config.source));
            return true;
        } else {
            source_status_ = "failed: "+source_->last_error();
            spdlog::warn("Failed to open {}: {} retry {}/{}", mask_url(config.source), source_->last_error(), retries, config.pipeline.reconnect.max_retries);
            retries++;
            if (retries > config.pipeline.reconnect.max_retries) return false;
            std::this_thread::sleep_for(std::chrono::duration<float>(delay));
            delay = std::min(delay*config.pipeline.reconnect.backoff_base, config.pipeline.reconnect.max_delay);
        }
    }
    return false;
}

bool DetectionPipeline::start() {
    spdlog::info("Starting pipeline source={} model={} device={}", mask_url(config.source), config.model.path, config.device);
    if (!detector_->load()) {
        spdlog::error("Detector load failed");
        return false;
    }
    detector_->warmup(config.warmup);
    if (logger_) logger_->start();

    if (!open_source_with_retry()) {
        spdlog::error("Failed to open source after retries");
        return false;
    }

    stop_flag_=false;
    capture_thread_ = std::thread(&DetectionPipeline::capture_loop, this);
    inference_thread_ = std::thread(&DetectionPipeline::inference_loop, this);
    render_thread_ = std::thread(&DetectionPipeline::render_loop, this);
    return true;
}

void DetectionPipeline::stop() {
    stop_flag_=true;
    if (capture_thread_.joinable()) capture_thread_.join();
    if (inference_thread_.joinable()) inference_thread_.join();
    if (render_thread_.joinable()) render_thread_.join();
    if (source_) source_->close();
    if (logger_) logger_->stop();
    if (video_writer_.isOpened()) video_writer_.release();
    spdlog::info("Pipeline stopped");
}

void DetectionPipeline::capture_loop() {
    int consecutive_failures=0;
    while(!stop_flag_.load()) {
        if (pause_flag_.load()) { std::this_thread::sleep_for(std::chrono::milliseconds(10)); continue; }

        cv::Mat frame;
        bool ok = source_->read(frame);
        if (!ok || frame.empty()) {
            consecutive_failures++;
            source_status_ = "read_fail "+std::to_string(consecutive_failures);
            spdlog::warn("Source read failed {}", consecutive_failures);
            if (source_->is_live() && config.pipeline.reconnect.enabled) {
                source_->close();
                std::this_thread::sleep_for(std::chrono::duration<float>(config.pipeline.reconnect.initial_delay));
                if (!open_source_with_retry()) {
                    spdlog::error("Reconnect failed, stopping");
                    stop_flag_=true;
                    break;
                }
                consecutive_failures=0;
                continue;
            } else {
                // EOF
                spdlog::info("End of source");
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
                if (!source_->is_live()) { stop_flag_=true; break; }
                continue;
            }
        }
        consecutive_failures=0;
        source_status_="ok";
        // ROI
        if (config.roi) {
            auto r = *config.roi;
            cv::Rect roi(r[0], r[1], r[2]-r[0], r[3]-r[1]);
            roi = roi & cv::Rect(0,0,frame.cols, frame.rows);
            if (roi.width>0 && roi.height>0) frame = frame(roi);
        }
        // frame skip
        if (config.frame_skip>0) {
            if (frame_counter_ % (config.frame_skip+1) !=0) { frame_counter_++; continue; }
        }
        frame_counter_++;
        FramePacket pkt;
        pkt.frame_id = frame_counter_;
        pkt.frame = frame;
        pkt.timestamp_capture = now_seconds();
        pkt.source_status = source_status_;
        capture_queue_.put(std::move(pkt));
    }
    spdlog::info("Capture loop ended");
}

void DetectionPipeline::inference_loop() {
    std::vector<double> latency_buf;
    std::vector<double> inf_time_buf;
    auto last_fps_time = std::chrono::steady_clock::now();
    int fps_count=0;

    while(!stop_flag_.load()) {
        FramePacket pkt;
        if (!capture_queue_.get(pkt, 200)) continue;
        try {
            auto t0 = std::chrono::steady_clock::now();
            FrameResult result = detector_->detect(pkt.frame, pkt.frame_id);
            auto t1 = std::chrono::steady_clock::now();
            double latency_ms = (now_seconds() - pkt.timestamp_capture)*1000.0;

            // simple tracking (IoU)
            // (omitted for brevity, could add IoU tracker)

            if (logger_) logger_->log(result, latency_ms);

            InferencePacket ip;
            ip.frame_packet = pkt;
            ip.result = result;
            ip.timestamp_done = now_seconds();
            inference_queue_.put(std::move(ip));

            // fps calc
            fps_count++;
            auto now = std::chrono::steady_clock::now();
            double elapsed = std::chrono::duration<double>(now-last_fps_time).count();
            if (elapsed>=1.0) {
                fps_ = fps_count / elapsed;
                // use inference time for inf_fps approx
                inf_fps_ = fps_; // simplified
                avg_latency_ = latency_ms;
                fps_count=0;
                last_fps_time=now;
            }

        } catch (const std::exception& e) {
            spdlog::error("Inference error: {}", e.what());
        }
    }
}

void DetectionPipeline::render_loop() {
    // init video writer lazily
    while(!stop_flag_.load()) {
        InferencePacket pkt;
        if (!inference_queue_.get(pkt, 200)) continue;
        try {
            if (config.output.save_video && !video_writer_.isOpened()) {
                int w = pkt.frame_packet.frame.cols;
                int h = pkt.frame_packet.frame.rows;
                int fourcc = cv::VideoWriter::fourcc('m','p','4','v');
                video_writer_.open(*config.output.save_video, fourcc, 30.0, cv::Size(w,h));
                if (!video_writer_.isOpened()) {
                    spdlog::warn("Failed to open video writer {}", *config.output.save_video);
                }
            }
            if (video_writer_.isOpened()) {
                // save annotated? We'll save after drawing in app; for now save raw
                // Actual drawing done in GUI thread; so we don't write here, but we could
                // For simplicity write raw frame
                // video_writer_.write(pkt.frame_packet.frame);
            }
            render_queue_.put(std::move(pkt));
        } catch (const std::exception& e) {
            spdlog::error("Render loop error: {}", e.what());
        }
    }
}

bool DetectionPipeline::get_latest(InferencePacket& out, int timeout_ms) {
    return render_queue_.get(out, timeout_ms);
}

}
