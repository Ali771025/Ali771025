#pragma once
#include "isource.h"
#include <memory>
#include <string>

namespace yolo {
std::unique_ptr<ISource> create_source(const std::string& source, const std::string& source_type="auto", int timeout_ms=5000);
}
