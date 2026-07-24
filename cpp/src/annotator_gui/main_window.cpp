#ifdef YOLO_GUI_QT
#include "yolo/annotator_gui/main_window.h"
#include "yolo/annotator_core/auto_labeler.h"
#include "yolo/annotator_core/exporters.h"
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QFileDialog>
#include <QMessageBox>
#include <QToolBar>
#include <QSplitter>
#include <QImage>
#include <QPixmap>
#include <opencv2/imgproc.hpp>
#include <opencv2/imgcodecs.hpp>

namespace yolo {
namespace annotator {

AnnotatorMainWindow::AnnotatorMainWindow(const std::string& project_path, const std::string& model_path, QWidget* parent)
    : QMainWindow(parent), project_path_(project_path), model_path_(model_path), project_(project_path, {"person","car"}), auto_labeler_(nullptr)
{
    setWindowTitle("Offline YOLO Annotator C++");
    resize(1600,900);

    // try to open existing
    try {
        if (std::filesystem::exists(project_path+"/project.yaml")) project_ = AnnotationProject::open(project_path);
        else project_ = AnnotationProject::create(project_path, {"person","car","bicycle","dog","cat"});
    } catch(...) { project_ = AnnotationProject::create(project_path, {"person","car"}); }

    auto central = new QWidget(this);
    setCentralWidget(central);
    auto main_layout = new QHBoxLayout(central);
    auto splitter = new QSplitter(Qt::Horizontal, this);

    // left image list
    image_list_ = new QListWidget(this);
    splitter->addWidget(image_list_);

    // center image
    image_label_ = new QLabel(this);
    image_label_->setAlignment(Qt::AlignCenter);
    image_label_->setStyleSheet("background-color: #222;");
    image_label_->setMinimumSize(640,480);
    splitter->addWidget(image_label_);

    // right object list
    object_list_ = new QListWidget(this);
    splitter->addWidget(object_list_);

    splitter->setSizes({300,900,300});
    main_layout->addWidget(splitter);

    // toolbar
    auto toolbar = new QToolBar("Main", this);
    addToolBar(toolbar);
    auto act_open = toolbar->addAction("Open Project");
    connect(act_open, &QAction::triggered, this, &AnnotatorMainWindow::open_project);
    auto act_import = toolbar->addAction("Import Images");
    connect(act_import, &QAction::triggered, this, &AnnotatorMainWindow::import_images);
    auto act_import_vid = toolbar->addAction("Import Video");
    connect(act_import_vid, &QAction::triggered, this, &AnnotatorMainWindow::import_video);
    auto act_auto = toolbar->addAction("Auto-Label All");
    connect(act_auto, &QAction::triggered, this, &AnnotatorMainWindow::auto_label_all);
    auto act_export_yolo = toolbar->addAction("Export YOLO");
    connect(act_export_yolo, &QAction::triggered, this, &AnnotatorMainWindow::export_yolo);
    auto act_export_coco = toolbar->addAction("Export COCO");
    connect(act_export_coco, &QAction::triggered, this, &AnnotatorMainWindow::export_coco);
    auto act_export_voc = toolbar->addAction("Export VOC");
    connect(act_export_voc, &QAction::triggered, this, &AnnotatorMainWindow::export_voc);
    auto act_save = toolbar->addAction("Save");
    connect(act_save, &QAction::triggered, this, &AnnotatorMainWindow::save_project);

    connect(image_list_, &QListWidget::itemClicked, this, &AnnotatorMainWindow::on_image_selected);

    // auto labeler
    if (!model_path.empty() && std::filesystem::exists(model_path)) {
        auto_labeler_ = new AutoLabeler(model_path, "cpu", 0.3f, 0.45f);
        if (!auto_labeler_->load()) { delete auto_labeler_; auto_labeler_=nullptr; }
    }

    refresh_list();
}

AnnotatorMainWindow::~AnnotatorMainWindow() { if (auto_labeler_) delete auto_labeler_; }

void AnnotatorMainWindow::refresh_list() {
    image_list_->clear();
    auto list = project_.image_list();
    for(auto& img: list) {
        auto item = new QListWidgetItem(QString::fromStdString(std::filesystem::path(img.path).filename().string()+" ("+std::to_string(img.annotations.objects.size())+" objs)"));
        item->setData(Qt::UserRole, QString::fromStdString(img.path));
        image_list_->addItem(item);
    }
}

void AnnotatorMainWindow::load_image(const std::string& path) {
    current_path_ = path;
    current_image_ = cv::imread(path);
    if (current_image_.empty()) return;
    // draw boxes
    cv::Mat draw = current_image_.clone();
    // find info
    auto it = project_.images.find(path);
    std::vector<AnnotationObject> objs;
    if (it!=project_.images.end()) objs = it->second.annotations.objects;
    for(auto& obj: objs) {
        cv::rectangle(draw, cv::Point((int)obj.xyxy[0],(int)obj.xyxy[1]), cv::Point((int)obj.xyxy[2],(int)obj.xyxy[3]), cv::Scalar(0,255,0),2);
        cv::putText(draw, obj.class_name, cv::Point((int)obj.xyxy[0],(int)obj.xyxy[1]-5), cv::FONT_HERSHEY_SIMPLEX, 0.5, cv::Scalar(0,255,0),1);
    }
    cv::Mat rgb;
    cv::cvtColor(draw, rgb, cv::COLOR_BGR2RGB);
    QImage qimg(rgb.data, rgb.cols, rgb.rows, rgb.step, QImage::Format_RGB888);
    QImage copy = qimg.copy();
    QPixmap pix = QPixmap::fromImage(copy).scaled(image_label_->size(), Qt::KeepAspectRatio, Qt::SmoothTransformation);
    image_label_->setPixmap(pix);

    object_list_->clear();
    for(auto& obj: objs) {
        auto item = new QListWidgetItem(QString::fromStdString(obj.class_name+" ["+std::to_string((int)obj.xyxy[0])+","+std::to_string((int)obj.xyxy[1])+"] "+(obj.is_ai?"AI":"")));
        object_list_->addItem(item);
    }
}

void AnnotatorMainWindow::on_image_selected(QListWidgetItem* item) {
    std::string path = item->data(Qt::UserRole).toString().toStdString();
    load_image(path);
}

void AnnotatorMainWindow::open_project() {
    QString folder = QFileDialog::getExistingDirectory(this, "Open Project");
    if (folder.isEmpty()) return;
    project_path_ = folder.toStdString();
    try { project_ = AnnotationProject::open(project_path_); } catch(...) { project_ = AnnotationProject::create(project_path_, {}); }
    refresh_list();
}

void AnnotatorMainWindow::import_images() {
    QString folder = QFileDialog::getExistingDirectory(this, "Import Images");
    if (folder.isEmpty()) return;
    project_.import_images(folder.toStdString());
    refresh_list();
}

void AnnotatorMainWindow::import_video() {
    QString file = QFileDialog::getOpenFileName(this, "Import Video", "", "Videos (*.mp4 *.avi *.mkv *.mov)");
    if (file.isEmpty()) return;
    try {
        project_.import_video(file.toStdString(), 1.0f);
        refresh_list();
    } catch(const std::exception& e) {
        QMessageBox::warning(this, "Error", e.what());
    }
}

void AnnotatorMainWindow::auto_label_all() {
    if (!auto_labeler_) { QMessageBox::warning(this, "No Model", "Load model via --model"); return; }
    auto list = project_.image_list();
    for(auto& img: list) {
        auto dets = auto_labeler_->detect_image(img.path);
        // replace AI objects? keep human
        auto& stored = project_.images[img.path];
        std::vector<AnnotationObject> keep;
        for(auto& o: stored.annotations.objects) if (!o.is_ai) keep.push_back(o);
        keep.insert(keep.end(), dets.begin(), dets.end());
        stored.annotations.objects = keep;
    }
    refresh_list();
    if (!current_path_.empty()) load_image(current_path_);
}

void AnnotatorMainWindow::export_yolo() {
    QString out = QFileDialog::getExistingDirectory(this, "Export YOLO");
    if (out.isEmpty()) return;
    YOLOExporter ex(project_path_, project_.classes);
    ex.export_dataset(project_.image_list(), out.toStdString());
    QMessageBox::information(this, "Export", "Exported to "+out);
}

void AnnotatorMainWindow::export_coco() {
    QString file = QFileDialog::getSaveFileName(this, "Export COCO", "coco.json", "JSON (*.json)");
    if (file.isEmpty()) return;
    COCOExporter ex(project_.classes);
    ex.export_dataset(project_.image_list(), file.toStdString());
    QMessageBox::information(this, "Export", "Exported to "+file);
}

void AnnotatorMainWindow::export_voc() {
    QString out = QFileDialog::getExistingDirectory(this, "Export VOC");
    if (out.isEmpty()) return;
    VOCExporter ex(project_.classes);
    ex.export_dataset(project_.image_list(), out.toStdString());
    QMessageBox::information(this, "Export", "Exported to "+out);
}

void AnnotatorMainWindow::save_project() {
    project_.save();
}

}
}

#endif
