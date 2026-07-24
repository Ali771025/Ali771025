#include "yolo/core/logger.h"
#include "yolo/annotator_core/project.h"
#include "yolo/annotator_core/auto_labeler.h"
#include "yolo/annotator_core/exporters.h"
#include <CLI/CLI.hpp>
#include <spdlog/spdlog.h>
#include <filesystem>
#include <iostream>

#ifdef YOLO_GUI_QT
#include "yolo/annotator_gui/main_window.h"
#include <QApplication>

int main(int argc, char** argv) {
    std::string project_path="datasets/my_dataset";
    std::string model_path="models/yolov8n.onnx";
    std::string export_format="yolo";
    std::string export_path;
    std::string images_folder;
    bool headless=false;
    bool offline=true;

    CLI::App app{"Offline YOLO Annotator C++"};
    app.add_option("-p,--project", project_path, "Project folder");
    app.add_option("-m,--model", model_path, "YOLO model ONNX");
    app.add_option("--export-format", export_format, "Export format yolo,coco,voc");
    app.add_option("--export-path", export_path, "Export path");
    app.add_option("--images", images_folder, "Images folder to import");
    app.add_flag("--headless", headless, "Headless auto-label and export");
    app.add_flag("--offline", offline, "Offline mode");

    CLI11_PARSE(app, argc, argv);

    yolo::init_logger(false);

    if (headless) {
        // headless workflow similar to Python
        std::filesystem::create_directories(project_path);
        yolo::annotator::AnnotationProject proj = std::filesystem::exists(project_path+"/project.yaml") ? yolo::annotator::AnnotationProject::open(project_path) : yolo::annotator::AnnotationProject::create(project_path, {});
        if (!images_folder.empty()) proj.import_images(images_folder);
        if (!model_path.empty() && std::filesystem::exists(model_path)) {
            yolo::annotator::AutoLabeler labeler(model_path, "cpu", 0.3f, 0.45f);
            if (labeler.load()) {
                auto list = proj.image_list();
                for(auto& img: list) {
                    auto dets = labeler.detect_image(img.path);
                    // find in proj and update
                    if (proj.images.find(img.path)!=proj.images.end()) {
                        proj.images[img.path].annotations.objects.clear();
                        for(auto& d: dets) proj.images[img.path].annotations.objects.push_back(d);
                    }
                }
                spdlog::info("Auto-labeled {} images", list.size());
            }
        }
        std::string out = export_path.empty() ? project_path+"/export_"+export_format : export_path;
        auto list = proj.image_list();
        if (export_format=="yolo") {
            yolo::annotator::YOLOExporter ex(project_path, proj.classes);
            ex.export_dataset(list, out);
        } else if (export_format=="coco") {
            yolo::annotator::COCOExporter ex(proj.classes);
            std::string file = out; if (!file.ends_with(".json")) file+="/coco.json";
            ex.export_dataset(list, file);
        } else if (export_format=="voc") {
            yolo::annotator::VOCExporter ex(proj.classes);
            ex.export_dataset(list, out);
        }
        proj.save();
        spdlog::info("Exported to {}", out);
        return 0;
    }

    QApplication qapp(argc, argv);
    qapp.setStyleSheet("QWidget { background-color: #2b2b2b; color: #e0e0e0; } QPushButton { background-color: #3c3c3c; border: 1px solid #555; padding: 5px; } QListWidget { background-color: #353535; }");
    yolo::annotator::AnnotatorMainWindow win(project_path, model_path);
    win.show();
    return qapp.exec();
}
#else
int main(int argc, char** argv) {
    yolo::init_logger(false);
    std::string project_path="datasets/my_dataset";
    std::string model_path="models/yolov8n.onnx";
    std::string export_format="yolo";
    std::string export_path;
    std::string images_folder;
    bool headless=false;

    CLI::App app{"Offline YOLO Annotator C++ (no Qt)"};
    app.add_option("-p,--project", project_path, "Project folder");
    app.add_option("-m,--model", model_path, "YOLO model ONNX");
    app.add_option("--export-format", export_format, "Export format");
    app.add_option("--export-path", export_path, "Export path");
    app.add_option("--images", images_folder, "Images folder");
    app.add_flag("--headless", headless, "Headless");

    CLI11_PARSE(app, argc, argv);

    std::filesystem::create_directories(project_path);
    yolo::annotator::AnnotationProject proj = std::filesystem::exists(project_path+"/project.yaml") ? yolo::annotator::AnnotationProject::open(project_path) : yolo::annotator::AnnotationProject::create(project_path, {});
    if (!images_folder.empty()) proj.import_images(images_folder);
    if (!model_path.empty() && std::filesystem::exists(model_path)) {
        yolo::annotator::AutoLabeler labeler(model_path, "cpu", 0.3f, 0.45f);
        if (labeler.load()) {
            auto list = proj.image_list();
            for(auto& img: list) {
                auto dets = labeler.detect_image(img.path);
                if (proj.images.find(img.path)!=proj.images.end()) {
                    proj.images[img.path].annotations.objects.clear();
                    for(auto& d: dets) proj.images[img.path].annotations.objects.push_back(d);
                }
            }
        }
    }
    std::string out = export_path.empty() ? project_path+"/export_"+export_format : export_path;
    auto list = proj.image_list();
    if (export_format=="yolo") {
        yolo::annotator::YOLOExporter ex(project_path, proj.classes);
        ex.export_dataset(list, out);
    } else if (export_format=="coco") {
        yolo::annotator::COCOExporter ex(proj.classes);
        std::string file = out;
        if (!file.ends_with(".json")) file+="/coco.json";
        ex.export_dataset(list, file);
    } else if (export_format=="voc") {
        yolo::annotator::VOCExporter ex(proj.classes);
        ex.export_dataset(list, out);
    }
    proj.save();
    spdlog::info("Exported to {}", out);
    return 0;
}
#endif
