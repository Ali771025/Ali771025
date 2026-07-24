#pragma once
#include "annotation.h"
#include <string>
#include <vector>
#include <map>
#include <optional>

namespace yolo {
namespace annotator {

class AnnotationProject {
public:
    AnnotationProject(const std::string& project_path, const std::vector<std::string>& classes={});
    static AnnotationProject create(const std::string& path, const std::vector<std::string>& classes);
    static AnnotationProject open(const std::string& path);

    bool import_images(const std::string& folder, bool copy=false);
    int import_video(const std::string& video_path, float fps=1.0, const std::string& extract_dir="");
    void save();
    void scan_images();

    std::vector<ImageInfo> image_list() const;

    std::string project_path;
    std::string images_dir;
    std::string labels_dir;
    std::vector<std::string> classes;
    std::map<std::string, ImageInfo> images; // path -> info

private:
    std::string config_path_;
};

}
}
