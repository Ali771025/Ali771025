#include <gtest/gtest.h>
#include "yolo/logging/log_writer.h"
#include "yolo/core/common.h"
#include <filesystem>

TEST(LogWriterTest, Jsonl) {
    std::string path="/tmp/test_log.jsonl";
    yolo::LogWriter writer(path, "jsonl", "test_src", "usb", "yolov8n.onnx", "cpu");
    writer.start();
    yolo::FrameResult res;
    res.frame_id=1; res.width=640; res.height=480; res.timestamp_unix=yolo::now_seconds();
    yolo::Detection det;
    det.class_id=0; det.class_name="person"; det.confidence=0.9f;
    det.bbox={10,20,100,200}; det.xywh={10,20,90,180}; det.xywh_norm={0.1f,0.1f,0.2f,0.2f}; det.center={55,110}; det.area=90*180; det.track_id=1; det.model_name="yolov8n.onnx"; det.inference_time_ms=10;
    res.detections.push_back(det);
    writer.log(res, 15.0);
    std::this_thread::sleep_for(std::chrono::milliseconds(200));
    writer.stop();
    EXPECT_TRUE(std::filesystem::exists(path));
    std::filesystem::remove(path);
}
