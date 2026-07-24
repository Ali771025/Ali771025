#pragma once
#include <string>
#ifdef YOLO_GUI_QT
#include <QMainWindow>
#include <QLabel>
#include <QTimer>
#include <QSlider>
#include <opencv2/core.hpp>

namespace yolo {
class DetectionPipeline;

class MonitorWindow : public QMainWindow {
    Q_OBJECT
public:
    MonitorWindow(DetectionPipeline* pipeline, QWidget* parent=nullptr);
    ~MonitorWindow();

public slots:
    void update_frame();

private:
    DetectionPipeline* pipeline_;
    QLabel* image_label_;
    QLabel* status_label_;
    QSlider* conf_slider_;
    QTimer timer_;
    cv::Mat latest_frame_;
};

}
#endif
