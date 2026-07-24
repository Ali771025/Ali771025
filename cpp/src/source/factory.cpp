#include "yolo/source/factory.h"
#include "yolo/source/opencv_source.h"
#include <memory>

namespace yolo {

std::unique_ptr<ISource> create_source(const std::string& source, const std::string& source_type, int timeout_ms) {
    SourceType type = parse_source_type(source_type);
    if (type==SourceType::AUTO) type = guess_source_type(source);
    if (type==SourceType::IMAGES) {
        return std::make_unique<ImageFolderSource>(source);
    } else {
        return std::make_unique<OpenCVSource>(source, type, timeout_ms);
    }
}

}
