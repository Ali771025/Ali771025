#include "yolo/annotator_core/exporters.h"
#include <filesystem>
#include <fstream>
#include <nlohmann/json.hpp>
#include <opencv2/core.hpp>
#include <spdlog/spdlog.h>

namespace yolo {
namespace annotator {

YOLOExporter::YOLOExporter(const std::string& project_path, const std::vector<std::string>& classes): project_path_(project_path), classes_(classes) {}

std::string YOLOExporter::export_dataset(const std::vector<ImageInfo>& images, const std::string& output_dir) {
    namespace fs = std::filesystem;
    fs::create_directories(output_dir);
    fs::path labels_dir = fs::path(output_dir)/"labels";
    fs::create_directories(labels_dir);
    for(auto& img: images) {
        std::string stem = fs::path(img.path).stem().string();
        std::string label_file = (labels_dir/(stem+".txt")).string();
        std::ofstream fout(label_file);
        for(auto& obj: img.annotations.objects) {
            if (!obj.visible) continue;
            float cx = (obj.xyxy[0]+obj.xyxy[2])/2.0f / img.width;
            float cy = (obj.xyxy[1]+obj.xyxy[3])/2.0f / img.height;
            float w = (obj.xyxy[2]-obj.xyxy[0]) / img.width;
            float h = (obj.xyxy[3]-obj.xyxy[1]) / img.height;
            fout << obj.class_id << " " << cx << " " << cy << " " << w << " " << h << "\n";
        }
    }
    // dataset.yaml
    std::string yaml_path = (fs::path(output_dir)/"dataset.yaml").string();
    std::ofstream yout(yaml_path);
    yout << "path: " << output_dir << "\n";
    yout << "train: images\n";
    yout << "val: images\n";
    yout << "names:\n";
    for(size_t i=0;i<classes_.size();i++) yout << "  " << i << ": " << classes_[i] << "\n";
    return output_dir;
}

COCOExporter::COCOExporter(const std::vector<std::string>& classes): classes_(classes) {}
std::string COCOExporter::export_dataset(const std::vector<ImageInfo>& images, const std::string& output_path) {
    namespace fs = std::filesystem;
    fs::create_directories(fs::path(output_path).parent_path());
    nlohmann::json coco;
    coco["info"] = {{"description","offline-yolo export"},{"version","1.0"}};
    coco["licenses"] = nlohmann::json::array();
    coco["images"] = nlohmann::json::array();
    coco["annotations"] = nlohmann::json::array();
    coco["categories"] = nlohmann::json::array();
    for(size_t i=0;i<classes_.size();i++) {
        coco["categories"].push_back({{"id",i},{"name",classes_[i]},{"supercategory","none"}});
    }
    int ann_id=0;
    for(size_t img_id=0; img_id<images.size(); ++img_id) {
        auto& img = images[img_id];
        coco["images"].push_back({{"id",img_id},{"file_name",fs::path(img.path).filename().string()},{"width",img.width},{"height",img.height}});
        for(auto& obj: img.annotations.objects) {
            if (!obj.visible) continue;
            float x1=obj.xyxy[0], y1=obj.xyxy[1], x2=obj.xyxy[2], y2=obj.xyxy[3];
            float w=x2-x1, h=y2-y1;
            nlohmann::json ann;
            ann["id"]=ann_id++; ann["image_id"]=img_id; ann["category_id"]=obj.class_id;
            ann["bbox"] = std::vector<float>{x1,y1,w,h};
            ann["area"]=w*h; ann["iscrowd"]=0;
            coco["annotations"].push_back(ann);
        }
    }
    std::ofstream fout(output_path);
    fout << coco.dump(2);
    return output_path;
}

VOCExporter::VOCExporter(const std::vector<std::string>& classes): classes_(classes) {}
std::string VOCExporter::export_dataset(const std::vector<ImageInfo>& images, const std::string& output_dir) {
    namespace fs = std::filesystem;
    fs::create_directories(output_dir);
    for(auto& img: images) {
        std::string xml_content = "<annotation>\n";
        xml_content += "  <folder>"+fs::path(img.path).parent_path().filename().string()+"</folder>\n";
        xml_content += "  <filename>"+fs::path(img.path).filename().string()+"</filename>\n";
        xml_content += "  <size><width>"+std::to_string(img.width)+"</width><height>"+std::to_string(img.height)+"</height><depth>3</depth></size>\n";
        for(auto& obj: img.annotations.objects) {
            if (!obj.visible) continue;
            xml_content += "  <object><name>"+obj.class_name+"</name><pose>Unspecified</pose><truncated>0</truncated><difficult>0</difficult><bndbox>";
            xml_content += "<xmin>"+std::to_string((int)obj.xyxy[0])+"</xmin><ymin>"+std::to_string((int)obj.xyxy[1])+"</ymin><xmax>"+std::to_string((int)obj.xyxy[2])+"</xmax><ymax>"+std::to_string((int)obj.xyxy[3])+"</ymax>";
            xml_content += "</bndbox></object>\n";
        }
        xml_content += "</annotation>\n";
        std::string out_file = (fs::path(output_dir)/(fs::path(img.path).stem().string()+".xml")).string();
        std::ofstream fout(out_file);
        fout << xml_content;
    }
    return output_dir;
}

}
}
