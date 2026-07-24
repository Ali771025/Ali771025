#ifdef YOLO_GUI_QT
#include "yolo/gui/monitor_window.h"
#include "yolo/core/config.h"
#include "yolo/pipeline/pipeline.h"
#include "yolo/core/logger.h"
#include <CLI/CLI.hpp>
#include <QApplication>
#include <spdlog/spdlog.h>

int main(int argc, char** argv) {
    yolo::AppConfig cfg;
    std::string config_path, source_override, model_override, device_override;
    CLI::App app{"YOLO GUI Monitor"};
    app.add_option("-c,--config", config_path, "Config yaml");
    app.add_option("-s,--source", source_override, "Source");
    app.add_option("-m,--model", model_override, "Model");
    app.add_option("--device", device_override, "Device");
    CLI11_PARSE(app, argc, argv);
    if (!config_path.empty()) cfg = yolo::AppConfig::from_yaml(config_path);
    if (!source_override.empty()) cfg.source = source_override;
    if (!model_override.empty()) cfg.model.path = model_override;
    if (!device_override.empty()) cfg.device = device_override;

    yolo::init_logger(false);
    yolo::DetectionPipeline pipeline(cfg);
    if (!pipeline.start()) return 1;

    QApplication qapp(argc, argv);
    yolo::MonitorWindow win(&pipeline);
    win.show();
    int ret = qapp.exec();
    pipeline.stop();
    return ret;
}
#else
#include <iostream>
int main(){ std::cout<<"Qt GUI not compiled. Build with -DYOLO_WITH_QT=ON\n"; return 0; }
#endif
