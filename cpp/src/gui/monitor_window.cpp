#ifdef YOLO_GUI_QT
#include "yolo/gui/monitor_window.h"
#include "yolo/pipeline/pipeline.h"
#include "yolo/core/common.h"
#include <QImage>
#include <QPixmap>
#include <opencv2/imgproc.hpp>

namespace yolo {

MonitorWindow::MonitorWindow(DetectionPipeline* pipeline, QWidget* parent)
    : QMainWindow(parent), pipeline_(pipeline) {
    setWindowTitle("YOLO Monitor Qt");
    resize(1280,720);
    auto central = new QWidget(this);
    setCentralWidget(central);
    auto layout = new QVBoxLayout(central);
    image_label_ = new QLabel(this);
    image_label_->setAlignment(Qt::AlignCenter);
    image_label_->setStyleSheet("background-color: #222;");
    layout->addWidget(image_label_);
    status_label_ = new QLabel("Starting...", this);
    layout->addWidget(status_label_);
    conf_slider_ = new QSlider(Qt::Horizontal, this);
    conf_slider_->setRange(0,100);
    conf_slider_->setValue(35);
    layout->addWidget(conf_slider_);

    connect(&timer_, &QTimer::timeout, this, &MonitorWindow::update_frame);
    timer_.start(30);
}

MonitorWindow::~MonitorWindow() = default;

void MonitorWindow::update_frame() {
    InferencePacket pkt;
    if (!pipeline_->get_latest(pkt, 10)) return;
    cv::Mat frame = pkt.frame_packet.frame.clone();
    // draw detections simple
    for(auto& det: pkt.result.detections) {
        cv::rectangle(frame, cv::Point((int)det.bbox.x1,(int)det.bbox.y1), cv::Point((int)det.bbox.x2,(int)det.bbox.y2), cv::Scalar(0,255,0),2);
        cv::putText(frame, det.class_name+" "+std::to_string(int(det.confidence*100))+"%", cv::Point((int)det.bbox.x1,(int)det.bbox.y1-5), cv::FONT_HERSHEY_SIMPLEX, 0.5, cv::Scalar(0,255,0),1);
    }
    cv::Mat rgb;
    cv::cvtColor(frame, rgb, cv::COLOR_BGR2RGB);
    QImage qimg(rgb.data, rgb.cols, rgb.rows, rgb.step, QImage::Format_RGB888);
    QImage copy = qimg.copy();
    QPixmap pix = QPixmap::fromImage(copy).scaled(image_label_->size(), Qt::KeepAspectRatio, Qt::SmoothTransformation);
    image_label_->setPixmap(pix);
    status_label_->setText(QString("FPS: %1 INF: %2 Dets: %3 Status: %4").arg(pipeline_->fps()).arg(pipeline_->inf_fps()).arg(pkt.result.detections.size()).arg(QString::fromStdString(pipeline_->source_status())));
}

}
#endif
