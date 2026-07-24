#pragma once
#include <string>
#include <vector>
#include <optional>
#include <chrono>

namespace yolo {

inline std::string mask_url(const std::string& url) {
    if (url.empty()) return url;
    // mask rtsp://user:pass@...
    auto pos = url.find("://");
    if (pos == std::string::npos) return url;
    auto at = url.find('@', pos+3);
    if (at == std::string::npos) return url;
    auto colon = url.rfind(':', at);
    if (colon == std::string::npos || colon < pos) return url;
    // user:pass@
    std::string masked = url.substr(0, colon+1) + "****@" + url.substr(at+1);
    return masked;
}

inline double now_seconds() {
    using namespace std::chrono;
    return duration<double>(system_clock::now().time_since_epoch()).count();
}

}
