#pragma once
#include "annotation.h"
#include <string>
#include <vector>

namespace yolo {
namespace annotator {

class YOLOExporter {
public:
    YOLOExporter(const std::string& project_path, const std::vector<std::string>& classes);
    std::string export_dataset(const std::vector<ImageInfo>& images, const std::string& output_dir);
private:
    std::string project_path_;
    std::vector<std::string> classes_;
};

class COCOExporter {
public:
    COCOExporter(const std::vector<std::string>& classes);
    std::string export_dataset(const std::vector<ImageInfo>& images, const std::string& output_path);
private:
    std::vector<std::string> classes_;
};

class VOCExporter {
public:
    VOCExporter(const std::vector<std::string>& classes);
    std::string export_dataset(const std::vector<ImageInfo>& images, const std::string& output_dir);
private:
    std::vector<std::string> classes_;
};

}
}
