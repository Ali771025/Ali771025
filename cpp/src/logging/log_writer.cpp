#include <nlohmann/json.hpp>
#include "yolo/logging/log_writer.h"
#include "yolo/core/common.h"
#include <nlohmann/json.hpp>
#include <chrono>
#include <iomanip>
#include <filesystem>
#include <spdlog/spdlog.h>

namespace yolo {

LogWriter::LogWriter(const std::string& path, const std::string& format, const std::string& source_id, const std::string& source_type, const std::string& model_name, const std::string& device)
    : path_(path), format_(format), source_id_(source_id), source_type_(source_type), model_name_(model_name), device_(device) {}

LogWriter::~LogWriter() { stop(); }

void LogWriter::start() {
    if (path_.empty()) return;
    std::filesystem::create_directories(std::filesystem::path(path_).parent_path());
    if (format_=="csv") {
        file_.open(path_);
    } else if (format_=="jsonl" || format_=="json") {
        file_.open(path_);
    } else if (format_=="both") {
        file_.open(path_);
        std::string csv_path = std::filesystem::path(path_).replace_extension(".csv").string();
        csv_file_.open(csv_path);
    } else if (format_=="sqlite") {
        // sqlite handling would require sqlite3 lib; for simplicity write jsonl fallback
        spdlog::warn("SQLite logging requested but not implemented, fallback to jsonl");
        file_.open(path_);
    }
    running_=true;
    stop_=false;
    thread_ = std::thread(&LogWriter::worker, this);
}

void LogWriter::stop() {
    if (!running_) return;
    stop_=true;
    cv_.notify_all();
    if (thread_.joinable()) thread_.join();
    if (file_.is_open()) file_.close();
    if (csv_file_.is_open()) csv_file_.close();
    running_=false;
}

void LogWriter::log(const FrameResult& result, double latency_ms) {
    if (path_.empty() || !running_) return;
    double ts_unix = result.timestamp_unix;
    // iso time
    auto tp = std::chrono::system_clock::from_time_t((time_t)ts_unix);
    auto ms = (int)((ts_unix - (long)ts_unix)*1000);
    std::time_t t = (time_t)ts_unix;
    std::tm tm = *std::gmtime(&t);
    char buf[64];
    std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%S", &tm);
    std::string iso = std::string(buf) + "." + std::to_string(ms) + "Z";

    for(auto& det: result.detections) {
        nlohmann::json j;
        j["timestamp_unix"]=ts_unix;
        j["timestamp_iso"]=iso;
        j["source_id"]=source_id_;
        j["source_type"]=source_type_;
        j["frame_id"]=result.frame_id;
        j["frame_width"]=result.width;
        j["frame_height"]=result.height;
        j["model_name"]=det.model_name.empty()? model_name_: det.model_name;
        j["device"]=device_;
        j["backend"]=device_;
        j["class_id"]=det.class_id;
        j["class_name"]=det.class_name;
        j["confidence"]=det.confidence;
        j["x1"]=det.bbox.x1; j["y1"]=det.bbox.y1; j["x2"]=det.bbox.x2; j["y2"]=det.bbox.y2;
        j["x"]=det.xywh[0]; j["y"]=det.xywh[1]; j["w"]=det.xywh[2]; j["h"]=det.xywh[3];
        j["cx"]=det.xywh_norm[0]; j["cy"]=det.xywh_norm[1]; j["nw"]=det.xywh_norm[2]; j["nh"]=det.xywh_norm[3];
        j["center_x"]=det.center[0]; j["center_y"]=det.center[1];
        j["area"]=det.area; j["aspect_ratio"]=det.aspect_ratio;
        j["track_id"]=det.track_id;
        j["inference_time_ms"]=det.inference_time_ms;
        j["latency_ms"]=latency_ms;
        j["bbox_xyxy"]=std::vector<float>{det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2};
        j["bbox_xywh"]=std::vector<float>{det.xywh[0],det.xywh[1],det.xywh[2],det.xywh[3]};
        j["bbox_normalized_xywh"]=std::vector<float>{det.xywh_norm[0],det.xywh_norm[1],det.xywh_norm[2],det.xywh_norm[3]};

        {
            std::lock_guard<std::mutex> lk(mtx_);
            if (queue_.size() < 10000) queue_.push(j);
        }
        cv_.notify_one();
    }
}

void LogWriter::worker() {
    while(!stop_ || !queue_.empty()) {
        nlohmann::json item;
        {
            std::unique_lock<std::mutex> lk(mtx_);
            if (queue_.empty()) {
                cv_.wait_for(lk, std::chrono::milliseconds(100), [this]{return !queue_.empty() || stop_;});
                if (queue_.empty()) continue;
            }
            item = queue_.front(); queue_.pop();
        }
        try {
            if (format_=="csv" || format_=="both") {
                // csv writer - header on first write
                if (!csv_header_written_) {
                    // write header
                    bool first=true;
                    std::string header;
                    for(auto& [k,v]: item.items()) {
                        if (!first) { if (format_=="csv") file_ << ","; else csv_file_ << ","; }
                        if (format_=="csv") file_ << k; else csv_file_ << k;
                        if (first) header+=k; else header+=","+k;
                        first=false;
                    }
                    if (format_=="csv") file_ << "\n";
                    else {
                        if (csv_file_.is_open()) csv_file_ << header << "\n";
                        // also for both, we still need json file separate?
                    }
                    csv_header_written_=true;
                }
                // write row
                auto write_row = [&](std::ofstream& f){
                    bool first=true;
                    for(auto& [k,v]: item.items()) {
                        if (!first) f << ",";
                        if (v.is_string()) f << "\"" << v.get<std::string>() << "\"";
                        else f << v;
                        first=false;
                    }
                    f << "\n";
                    f.flush();
                };
                if (format_=="csv") {
                    write_row(file_);
                } else if (format_=="both") {
                    // json part
                    file_ << item.dump() << "\n"; file_.flush();
                    if (csv_file_.is_open()) write_row(csv_file_);
                }
            } else {
                // jsonl
                file_ << item.dump() << "\n";
                file_.flush();
            }
        } catch (const std::exception& e) {
            spdlog::error("LogWriter error: {}", e.what());
        }
    }
}

}
