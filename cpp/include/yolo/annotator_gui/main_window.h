#pragma once
#include <string>

#ifdef YOLO_GUI_QT
#include <QMainWindow>
#include <QLabel>
#include <QListWidget>
#include <QPushButton>
#include "yolo/annotator_core/project.h"

namespace yolo {
namespace annotator {

class AnnotatorMainWindow : public QMainWindow {
    Q_OBJECT
public:
    AnnotatorMainWindow(const std::string& project_path, const std::string& model_path="", QWidget* parent=nullptr);
    ~AnnotatorMainWindow();

private slots:
    void open_project();
    void import_images();
    void import_video();
    void auto_label_all();
    void export_yolo();
    void export_coco();
    void export_voc();
    void on_image_selected(QListWidgetItem* item);
    void save_project();

private:
    void refresh_list();
    void load_image(const std::string& path);

    std::string project_path_;
    std::string model_path_;
    AnnotationProject project_;
    QLabel* image_label_;
    QListWidget* image_list_;
    QListWidget* object_list_;
    cv::Mat current_image_;
    std::string current_path_;
    class AutoLabeler* auto_labeler_{nullptr};
};

}
}
#else
namespace yolo { namespace annotator { class AnnotatorMainWindow {}; } }
#endif
