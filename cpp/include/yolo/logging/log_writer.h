#pragma once
#include "yolo/core/detection.h"
#include <string>
#include <queue>
#include <thread>
#include <atomic>
#include <mutex>
#include <condition_variable>
#include <fstream>

namespace yolo {

class LogWriter {
public:
    LogWriter(const std::string& path, const std::string& format, const std::string& source_id, const std::string& source_type, const std::string& model_name, const std::string& device);
    ~LogWriter();

    void start();
    void stop();
    void log(const FrameResult& result, double latency_ms);

private:
    void worker();

    std::string path_;
    std::string format_;
    std::string source_id_;
    std::string source_type_;
    std::string model_name_;
    std::string device_;

    std::queue<nlohmann::json> queue_;
    std::mutex mtx_;
    std::condition_variable cv_;
    std::thread thread_;
    std::atomic<bool> stop_{false};
    bool running_{false};
    std::ofstream file_;
    std::ofstream csv_file_;
    bool csv_header_written_{false};
};

}
