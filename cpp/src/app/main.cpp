#include <filesystem>
#include "yolo/core/config.h"
#include "yolo/core/logger.h"
#include "yolo/pipeline/pipeline.h"
#include "yolo/core/common.h"
#include <CLI/CLI.hpp>
#include <spdlog/spdlog.h>
#include <opencv2/highgui.hpp>
#include <opencv2/imgproc.hpp>
#include <iostream>
#include <csignal>

static std::atomic<bool> g_stop{false};
void signal_handler(int) { g_stop=true; }

std::string get_color_name(int class_id) {
    static std::vector<std::string> colors = {"person","car"};
    return std::to_string(class_id);
}

cv::Scalar get_color(int idx) {
    static std::vector<cv::Scalar> palette = {
        {0,0,255},{0,255,0},{255,0,0},{0,255,255},{255,0,255},{255,255,0},
        {128,0,128},{0,128,255},{128,255,0},{255,0,128},{0,255,128}
    };
    return palette[idx % palette.size()];
}

void draw_detections(cv::Mat& frame, const yolo::FrameResult& result, const yolo::AppConfig& cfg) {
    for(auto& det: result.detections) {
        cv::Scalar color = get_color(det.class_id);
        cv::rectangle(frame, cv::Point((int)det.bbox.x1,(int)det.bbox.y1), cv::Point((int)det.bbox.x2,(int)det.bbox.y2), color, cfg.output.draw.line_thickness);
        if (cfg.output.draw.labels || cfg.output.draw.conf) {
            std::string label = det.class_name;
            if (cfg.output.draw.conf) label += " " + std::to_string(int(det.confidence*100)) + "%";
            if (cfg.output.draw.track_id && det.track_id>=0) label += " ID:"+std::to_string(det.track_id);
            int baseline;
            cv::Size ts = cv::getTextSize(label, cv::FONT_HERSHEY_SIMPLEX, cfg.output.draw.font_scale, 1, &baseline);
            cv::rectangle(frame, cv::Point((int)det.bbox.x1, (int)det.bbox.y1 - ts.height - baseline - 4), cv::Point((int)det.bbox.x1 + ts.width + 4, (int)det.bbox.y1), color, -1);
            cv::putText(frame, label, cv::Point((int)det.bbox.x1+2, (int)det.bbox.y1-4), cv::FONT_HERSHEY_SIMPLEX, cfg.output.draw.font_scale, cv::Scalar(255,255,255), 1, cv::LINE_AA);
        }
        if (cfg.output.draw.center) {
            cv::circle(frame, cv::Point((int)det.center[0], (int)det.center[1]), 3, color, -1);
        }
        if (cfg.output.draw.box_coords) {
            std::string coord = std::to_string((int)det.bbox.x1)+","+std::to_string((int)det.bbox.y1)+","+std::to_string((int)det.bbox.x2)+","+std::to_string((int)det.bbox.y2);
            cv::putText(frame, coord, cv::Point((int)det.bbox.x1, (int)det.bbox.y2+15), cv::FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv::LINE_AA);
        }
    }
}

void draw_overlay(cv::Mat& frame, double fps, double inf_fps, double latency, const std::string& source_info, const std::string& model_info, const std::string& device, float conf, float iou, int count, const std::string& res) {
    int h = frame.rows, w = frame.cols;
    int panel_h = 80;
    cv::rectangle(frame, cv::Point(0,0), cv::Point(w,panel_h), cv::Scalar(0,0,0), -1);
    cv::rectangle(frame, cv::Point(0,0), cv::Point(w,panel_h), cv::Scalar(50,50,50), 1);
    std::string t1 = "FPS: "+std::to_string((int)fps)+" | INF: "+std::to_string((int)inf_fps)+" | Lat: "+std::to_string((int)latency)+"ms";
    std::string t2 = "SRC: "+source_info+" | "+res;
    std::string t3 = "MODEL: "+model_info+" | DEV: "+device+" | CONF:"+std::to_string(conf).substr(0,4)+" IOU:"+std::to_string(iou).substr(0,4);
    std::string t4 = "DETS: "+std::to_string(count);
    cv::putText(frame, t1, cv::Point(10,15), cv::FONT_HERSHEY_SIMPLEX, 0.5, cv::Scalar(0,255,0), 1, cv::LINE_AA);
    cv::putText(frame, t2, cv::Point(10,35), cv::FONT_HERSHEY_SIMPLEX, 0.5, cv::Scalar(0,255,0), 1, cv::LINE_AA);
    cv::putText(frame, t3, cv::Point(10,55), cv::FONT_HERSHEY_SIMPLEX, 0.5, cv::Scalar(0,255,0), 1, cv::LINE_AA);
    cv::putText(frame, t4, cv::Point(10,75), cv::FONT_HERSHEY_SIMPLEX, 0.5, cv::Scalar(0,255,0), 1, cv::LINE_AA);
}

int main(int argc, char** argv) {
    yolo::AppConfig cfg;
    std::string config_path;
    std::string source_override;
    std::string source_type_override="auto";
    std::string model_override;
    std::string backend_override="auto";
    std::string device_override="auto";
    float conf_override = -1;
    float iou_override = -1;
    std::string log_path;
    std::string log_format="jsonl";
    bool show=true;
    std::string save_video;
    bool verbose=false;
    bool offline=false;

    CLI::App app{"Offline YOLO Monitor C++"};
    app.add_option("-c,--config", config_path, "YAML config file");
    app.add_option("-s,--source", source_override, "Source: 0, /dev/video0, rtsp://..., http://..., video.mp4, folder");
    app.add_option("--source-type", source_type_override, "Source type auto, usb, v4l2, rtsp, http, video, images, gstreamer");
    app.add_option("-m,--model", model_override, "Model path .onnx, .engine");
    app.add_option("--backend", backend_override, "Backend auto, onnx, opencv, tensorrt");
    app.add_option("--device", device_override, "Device auto, cpu, cuda");
    app.add_option("--conf", conf_override, "Confidence threshold");
    app.add_option("--iou", iou_override, "IoU threshold");
    app.add_option("--log", log_path, "Log path .csv/.jsonl");
    app.add_option("--log-format", log_format, "Log format csv, jsonl, both");
    app.add_option("--save-video", save_video, "Save video path");
    app.add_flag("--show,!--no-show", show, "Show window");
    app.add_flag("-v,--verbose", verbose, "Verbose");
    app.add_flag("--offline", offline, "Offline mode");

    try { app.parse(argc, argv); } catch(const CLI::ParseError &e){ return app.exit(e); }

    yolo::init_logger(verbose);

    if (!config_path.empty()) {
        try {
            cfg = yolo::AppConfig::from_yaml(config_path);
        } catch (const std::exception& e) {
            spdlog::error("Failed to load config {}: {}", config_path, e.what());
            return 1;
        }
    }

    if (!source_override.empty()) cfg.source = source_override;
    if (!source_type_override.empty()) cfg.source_type = source_type_override;
    if (!model_override.empty()) cfg.model.path = model_override;
    if (!backend_override.empty()) cfg.model.backend = backend_override;
    if (!device_override.empty()) cfg.device = device_override;
    if (conf_override>=0) cfg.conf_thres = conf_override;
    if (iou_override>=0) cfg.iou_thres = iou_override;
    if (!log_path.empty()) cfg.output.log_path = log_path;
    cfg.output.log_format = log_format;
    if (!save_video.empty()) cfg.output.save_video = save_video;
    cfg.output.show = show;
    cfg.verbose = verbose;
    cfg.offline = offline;

    // check model exists
    if (!std::filesystem::exists(cfg.model.path)) {
        spdlog::warn("Model not found: {}. Ensure it exists for offline use.", cfg.model.path);
    }

    yolo::DetectionPipeline pipeline(cfg);
    if (!pipeline.start()) {
        spdlog::error("Failed to start pipeline");
        return 1;
    }

    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    std::string window_name = "YOLO Monitor C++ - " + cfg.model.path + " - " + cfg.source;
    bool paused=false;
    bool conf_changed=false;

    // For FPS calc
    auto fps_tracker_last = std::chrono::steady_clock::now();
    int fps_counter=0;
    double fps=0;

    while(!g_stop && !pipeline.is_stopped()) {
        yolo::InferencePacket pkt;
        if (!pipeline.get_latest(pkt, 100)) {
            if (show) {
                int key = cv::waitKey(1);
                if (key==27 || key=='q') break;
            }
            continue;
        }

        fps_counter++;
        auto now = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(now-fps_tracker_last).count();
        if (elapsed>=1.0) {
            fps = fps_counter/elapsed;
            fps_counter=0;
            fps_tracker_last=now;
        }

        cv::Mat frame = pkt.frame_packet.frame.clone();
        draw_detections(frame, pkt.result, cfg);

        if (cfg.output.draw.fps_overlay) {
            double latency = (yolo::now_seconds() - pkt.frame_packet.timestamp_capture)*1000.0;
            std::string res = std::to_string(pkt.result.width)+"x"+std::to_string(pkt.result.height);
            draw_overlay(frame, fps, pipeline.inf_fps(), latency, yolo::mask_url(cfg.source)+" "+pipeline.source_status(), cfg.model.path, cfg.device, cfg.conf_thres, cfg.iou_thres, (int)pkt.result.detections.size(), res);
        }

        if (show) {
            cv::imshow(window_name, frame);
            int key = cv::waitKey(1) & 0xFF;
            if (key==27 || key=='q') break;
            else if (key=='p') { paused=!paused; spdlog::info(paused?"Paused":"Resumed"); }
            else if (key=='s') {
                std::filesystem::create_directories("snapshots");
                std::string snap = "snapshots/snap_"+std::to_string((long)yolo::now_seconds())+".jpg";
                cv::imwrite(snap, frame);
                spdlog::info("Snapshot saved {}", snap);
            } else if (key=='+' || key=='=') { cfg.conf_thres = std::min(1.0f, cfg.conf_thres+0.05f); pipeline.detector()->conf_thres = cfg.conf_thres; spdlog::info("Conf {}", cfg.conf_thres); }
            else if (key=='-' || key=='_') { cfg.conf_thres = std::max(0.0f, cfg.conf_thres-0.05f); pipeline.detector()->conf_thres = cfg.conf_thres; spdlog::info("Conf {}", cfg.conf_thres); }
            else if (key==']') { cfg.iou_thres = std::min(1.0f, cfg.iou_thres+0.05f); pipeline.detector()->iou_thres = cfg.iou_thres; }
            else if (key=='[') { cfg.iou_thres = std::max(0.0f, cfg.iou_thres-0.05f); pipeline.detector()->iou_thres = cfg.iou_thres; }
            else if (key=='l') { cfg.output.draw.labels = !cfg.output.draw.labels; }
            else if (key=='f') { cfg.output.draw.fps_overlay = !cfg.output.draw.fps_overlay; }

            if (cv::getWindowProperty(window_name, cv::WND_PROP_VISIBLE) < 1) break;
        }

        // periodic log
        if (pkt.result.frame_id % 30 ==0) {
            spdlog::info("Frame {} FPS {:.1f} INF {:.1f} Dets {} Status {}", pkt.result.frame_id, fps, pipeline.inf_fps(), pkt.result.detections.size(), pipeline.source_status());
        }
    }

    pipeline.stop();
    if (show) cv::destroyAllWindows();
    spdlog::info("Exit");
    return 0;
}
