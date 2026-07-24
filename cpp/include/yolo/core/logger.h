#pragma once
#include <spdlog/spdlog.h>
#include <spdlog/sinks/stdout_color_sinks.h>

namespace yolo {
inline void init_logger(bool verbose=false) {
    auto logger = spdlog::stdout_color_mt("yolo");
    spdlog::set_default_logger(logger);
    spdlog::set_level(verbose ? spdlog::level::debug : spdlog::level::info);
    spdlog::set_pattern("[%Y-%m-%d %H:%M:%S.%e] [%^%l%$] %v");
}
}
