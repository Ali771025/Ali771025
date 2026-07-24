#include "yolo/annotator_core/project.h"
#include <filesystem>
#include <yaml-cpp/yaml.h>
#include <opencv2/videoio.hpp>
#include <opencv2/imgcodecs.hpp>
#include <spdlog/spdlog.h>

namespace yolo {
namespace annotator {

AnnotationProject::AnnotationProject(const std::string& project_path, const std::vector<std::string>& classes)
    : project_path(project_path), classes(classes) {
    images_dir = (std::filesystem::path(project_path) / "images").string();
    labels_dir = (std::filesystem::path(project_path) / "labels").string();
    config_path_ = (std::filesystem::path(project_path) / "project.yaml").string();
    if (this->classes.empty()) this->classes = {"person","car","bicycle","dog","cat"};
}

AnnotationProject AnnotationProject::create(const std::string& path, const std::vector<std::string>& classes) {
    std::filesystem::create_directories(path);
    std::filesystem::create_directories(std::filesystem::path(path)/"images");
    std::filesystem::create_directories(std::filesystem::path(path)/"labels");
    std::filesystem::create_directories(std::filesystem::path(path)/".backup");
    AnnotationProject proj(path, classes);
    proj.save();
    return proj;
}

AnnotationProject AnnotationProject::open(const std::string& path) {
    std::string cfg = (std::filesystem::path(path)/"project.yaml").string();
    if (!std::filesystem::exists(cfg)) {
        // if path is image folder, create project
        if (std::filesystem::is_directory(path)) {
            AnnotationProject proj = create(path, {});
            proj.import_images(path);
            return proj;
        }
        throw std::runtime_error("Project config not found: "+cfg);
    }
    YAML::Node node = YAML::LoadFile(cfg);
    std::vector<std::string> cls;
    if (node["classes"]) cls = node["classes"].as<std::vector<std::string>>();
    AnnotationProject proj(path, cls);
    proj.scan_images();
    return proj;
}

void AnnotationProject::scan_images() {
    namespace fs = std::filesystem;
    if (!fs::exists(images_dir)) return;
    std::vector<std::string> exts = {".jpg",".jpeg",".png",".bmp",".webp",".tiff"};
    for(auto& entry: fs::recursive_directory_iterator(images_dir)) {
        if (!entry.is_regular_file()) continue;
        auto ext = entry.path().extension().string();
        std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
        if (std::find(exts.begin(), exts.end(), ext)==exts.end()) continue;
        std::string p = entry.path().string();
        if (images.find(p)!=images.end()) continue;
        cv::Mat img = cv::imread(p);
        int w = img.cols, h = img.rows;
        ImageAnnotations ann;
        ann.image_path = p;
        ann.image_id = entry.path().stem().string();
        ann.width=w; ann.height=h;
        images[p] = ImageInfo{p,w,h,ann};
    }
}

bool AnnotationProject::import_images(const std::string& folder, bool copy) {
    namespace fs = std::filesystem;
    fs::path src(folder);
    if (!fs::exists(src)) return false;
    std::vector<std::string> exts = {".jpg",".jpeg",".png",".bmp",".webp",".tiff"};
    std::vector<fs::path> files;
    for(auto& entry: fs::recursive_directory_iterator(src)) {
        if (!entry.is_regular_file()) continue;
        auto ext = entry.path().extension().string();
        std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
        if (std::find(exts.begin(), exts.end(), ext)!=exts.end()) files.push_back(entry.path());
    }
    fs::create_directories(images_dir);
    for(auto& f: files) {
        std::string dest_path;
        if (copy) {
            fs::path dest = fs::path(images_dir)/f.filename();
            try { fs::copy_file(f, dest, fs::copy_options::overwrite_existing); dest_path = dest.string(); }
            catch(...) { dest_path = f.string(); }
        } else {
            dest_path = f.string();
        }
        if (images.find(dest_path)!=images.end()) continue;
        cv::Mat img = cv::imread(f.string());
        int w = img.cols, h = img.rows;
        ImageAnnotations ann; ann.image_path=dest_path; ann.image_id=f.stem().string(); ann.width=w; ann.height=h;
        images[dest_path] = ImageInfo{dest_path,w,h,ann};
    }
    return true;
}

int AnnotationProject::import_video(const std::string& video_path, float fps, const std::string& extract_dir) {
    cv::VideoCapture cap(video_path);
    if (!cap.isOpened()) throw std::runtime_error("Cannot open video "+video_path);
    double vid_fps = cap.get(cv::CAP_PROP_FPS);
    if (vid_fps<=0) vid_fps=30;
    int step = fps>0 ? std::max(1, int(vid_fps/fps)) : 1;
    std::string out_dir = extract_dir.empty() ? (std::filesystem::path(images_dir)/std::filesystem::path(video_path).stem()).string() : extract_dir;
    std::filesystem::create_directories(out_dir);
    int idx=0, saved=0;
    cv::Mat frame;
    while(cap.read(frame)) {
        if (idx % step==0) {
            std::string out_path = (std::filesystem::path(out_dir)/(std::filesystem::path(video_path).stem().string()+"_"+std::to_string(saved)+".jpg")).string();
            cv::imwrite(out_path, frame);
            ImageAnnotations ann; ann.image_path=out_path; ann.image_id=std::to_string(saved); ann.width=frame.cols; ann.height=frame.rows;
            images[out_path] = ImageInfo{out_path, frame.cols, frame.rows, ann};
            saved++;
        }
        idx++;
    }
    return saved;
}

void AnnotationProject::save() {
    YAML::Node node;
    node["name"] = std::filesystem::path(project_path).filename().string();
    node["classes"] = classes;
    node["images_dir"] = images_dir;
    node["labels_dir"] = labels_dir;
    std::filesystem::create_directories(std::filesystem::path(config_path_).parent_path());
    std::ofstream fout(config_path_);
    fout << node;
}

std::vector<ImageInfo> AnnotationProject::image_list() const {
    std::vector<ImageInfo> out;
    out.reserve(images.size());
    for(auto& [k,v]: images) out.push_back(v);
    return out;
}

}
}
