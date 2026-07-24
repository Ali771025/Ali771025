#pragma once
#include <opencv2/core.hpp>
#include <string>
#include <optional>

namespace yolo {

enum class SourceType { AUTO, USB, V4L2, RTSP, HTTP, VIDEO, IMAGES, GSTREAMER, RTMP };

class ISource {
public:
    virtual ~ISource() = default;
    virtual bool open() = 0;
    virtual bool read(cv::Mat& frame) = 0;
    virtual void close() = 0;
    virtual bool is_live() const = 0;
    virtual std::string info() const = 0;
    virtual std::pair<int,int> resolution() const = 0;
    virtual int frame_id() const = 0;
    virtual std::string last_error() const = 0;
};

SourceType guess_source_type(const std::string& src);
SourceType parse_source_type(const std::string& s);

}
