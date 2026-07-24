#pragma once
#include "isource.h"
#include <opencv2/videoio.hpp>

namespace yolo {

class OpenCVSource : public ISource {
public:
    OpenCVSource(const std::string& source, SourceType type, int timeout_ms=5000);
    bool open() override;
    bool read(cv::Mat& frame) override;
    void close() override;
    bool is_live() const override;
    std::string info() const override;
    std::pair<int,int> resolution() const override { return {width_, height_}; }
    int frame_id() const override { return frame_id_; }
    std::string last_error() const override { return last_error_; }

private:
    std::string source_;
    SourceType type_;
    int timeout_ms_;
    cv::VideoCapture cap_;
    int width_{0}, height_{0};
    double fps_{30};
    int frame_id_{0};
    std::string last_error_;
    bool is_open_{false};
};

class ImageFolderSource : public ISource {
public:
    ImageFolderSource(const std::string& source);
    bool open() override;
    bool read(cv::Mat& frame) override;
    void close() override;
    bool is_live() const override { return false; }
    std::string info() const override;
    std::pair<int,int> resolution() const override { return {width_, height_}; }
    int frame_id() const override { return frame_id_; }
    std::string last_error() const override { return last_error_; }

private:
    std::string source_;
    std::vector<std::string> files_;
    size_t idx_{0};
    int width_{0}, height_{0};
    int frame_id_{0};
    std::string last_error_;
    bool is_open_{false};
};

}
