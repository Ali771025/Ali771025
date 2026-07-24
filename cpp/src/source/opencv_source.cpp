#include "yolo/source/opencv_source.h"
#include "yolo/core/common.h"
#include <filesystem>
#include <spdlog/spdlog.h>
#include <opencv2/imgcodecs.hpp>

namespace yolo {

SourceType parse_source_type(const std::string& s) {
    std::string low=s;
    std::transform(low.begin(), low.end(), low.begin(), ::tolower);
    if (low=="auto") return SourceType::AUTO;
    if (low=="usb") return SourceType::USB;
    if (low=="v4l2") return SourceType::V4L2;
    if (low=="rtsp") return SourceType::RTSP;
    if (low=="http" || low=="mjpeg") return SourceType::HTTP;
    if (low=="video") return SourceType::VIDEO;
    if (low=="images") return SourceType::IMAGES;
    if (low=="gstreamer") return SourceType::GSTREAMER;
    if (low=="rtmp") return SourceType::RTMP;
    return SourceType::AUTO;
}

SourceType guess_source_type(const std::string& src) {
    if (src.empty()) return SourceType::USB;
    std::string s=src;
    // numeric?
    bool is_num=true;
    for(char c: s) if (!isdigit(c) && c!=' ') { is_num=false; break; }
    if (is_num) return SourceType::USB;
    if (s.rfind("dshow://",0)==0) return SourceType::USB;
    if (s.rfind("/dev/video",0)==0) return SourceType::V4L2;
    if (s.rfind("rtsp://",0)==0) return SourceType::RTSP;
    if (s.rfind("rtmp://",0)==0) return SourceType::RTMP;
    if (s.rfind("http://",0)==0 || s.rfind("https://",0)==0) return SourceType::HTTP;
    if (s.find('!')!=std::string::npos && (s.find("videoconvert")!=std::string::npos || s.find("v4l2src")!=std::string::npos)) return SourceType::GSTREAMER;
    try {
        std::filesystem::path p(s);
        if (std::filesystem::exists(p)) {
            if (std::filesystem::is_directory(p)) return SourceType::IMAGES;
            auto ext = p.extension().string();
            std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
            if (ext==".mp4"||ext==".avi"||ext==".mkv"||ext==".mov"||ext==".wmv"||ext==".flv"||ext==".webm") return SourceType::VIDEO;
            if (ext==".jpg"||ext==".jpeg"||ext==".png"||ext==".bmp"||ext==".tiff"||ext==".webp") return SourceType::IMAGES;
        }
    } catch(...) {}
    return SourceType::USB;
}

OpenCVSource::OpenCVSource(const std::string& source, SourceType type, int timeout_ms)
    : source_(source), type_(type), timeout_ms_(timeout_ms) {}

bool OpenCVSource::open() {
    try {
        std::string src = source_;
        // numeric?
        bool is_digit = true;
        for(char c: src) if (!isdigit(c)) { is_digit=false; break; }
        if (is_digit) {
            int idx = std::stoi(src);
            cap_.open(idx);
        } else if (src.rfind("dshow://",0)==0) {
            // parse index after //
            std::string num = src.substr(8);
            int idx = std::stoi(num);
            cap_.open(idx, cv::CAP_DSHOW);
        } else {
            if (type_==SourceType::GSTREAMER) {
                cap_.open(src, cv::CAP_GSTREAMER);
            } else {
                cap_.open(src);
            }
        }
        if (!cap_.isOpened()) {
            last_error_ = "Failed to open " + mask_url(src);
            return false;
        }
        // try set timeout if supported
        try {
            cap_.set(cv::CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms_);
            cap_.set(cv::CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms_);
        } catch(...) {}
        width_ = (int)cap_.get(cv::CAP_PROP_FRAME_WIDTH);
        height_ = (int)cap_.get(cv::CAP_PROP_FRAME_HEIGHT);
        fps_ = cap_.get(cv::CAP_PROP_FPS);
        if (fps_<=0) fps_=30;
        is_open_=true;
        frame_id_=0;
        spdlog::info("Opened source {} res {}x{} fps {}", mask_url(src), width_, height_, fps_);
        return true;
    } catch (const std::exception& e) {
        last_error_ = e.what();
        return false;
    }
}

bool OpenCVSource::read(cv::Mat& frame) {
    if (!is_open_) return false;
    bool ok = cap_.read(frame);
    if (ok && !frame.empty()) {
        frame_id_++;
        width_ = frame.cols;
        height_ = frame.rows;
        return true;
    }
    return false;
}

void OpenCVSource::close() {
    if (cap_.isOpened()) cap_.release();
    is_open_=false;
}

bool OpenCVSource::is_live() const {
    return type_==SourceType::USB || type_==SourceType::V4L2 || type_==SourceType::RTSP || type_==SourceType::HTTP || type_==SourceType::GSTREAMER || type_==SourceType::RTMP;
}

std::string OpenCVSource::info() const {
    return mask_url(source_);
}

ImageFolderSource::ImageFolderSource(const std::string& source) : source_(source) {}

bool ImageFolderSource::open() {
    try {
        std::filesystem::path p(source_);
        if (!std::filesystem::exists(p)) {
            last_error_="Folder not found: "+source_;
            return false;
        }
        if (std::filesystem::is_regular_file(p)) {
            files_.push_back(p.string());
        } else {
            std::vector<std::string> exts = {".jpg",".jpeg",".png",".bmp",".tiff",".webp"};
            for(auto& entry: std::filesystem::recursive_directory_iterator(p)) {
                if (!entry.is_regular_file()) continue;
                auto ext = entry.path().extension().string();
                std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
                if (std::find(exts.begin(), exts.end(), ext)!=exts.end()) {
                    files_.push_back(entry.path().string());
                }
            }
            std::sort(files_.begin(), files_.end());
        }
        if (files_.empty()) { last_error_="No images found in "+source_; return false; }
        idx_=0; frame_id_=0; is_open_=true;
        return true;
    } catch (const std::exception& e) {
        last_error_=e.what();
        return false;
    }
}

bool ImageFolderSource::read(cv::Mat& frame) {
    if (!is_open_ || idx_>=files_.size()) return false;
    std::string path = files_[idx_++];
    frame = cv::imread(path);
    if (frame.empty()) {
        // skip corrupt
        return read(frame);
    }
    frame_id_++;
    width_=frame.cols; height_=frame.rows;
    return true;
}

void ImageFolderSource::close() { is_open_=false; }

std::string ImageFolderSource::info() const {
    return "images:"+source_+" ("+std::to_string(idx_)+"/"+std::to_string(files_.size())+")";
}

}
