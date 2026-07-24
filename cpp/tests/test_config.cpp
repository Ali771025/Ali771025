#include <gtest/gtest.h>
#include "yolo/core/config.h"
#include <fstream>

TEST(ConfigTest, Default) {
    yolo::AppConfig cfg;
    EXPECT_EQ(cfg.imgsz, 640);
    EXPECT_FLOAT_EQ(cfg.conf_thres, 0.35f);
}

TEST(ConfigTest, Yaml) {
    std::string yaml_content = "source: \"0\"\nmodel:\n  path: \"models/test.onnx\"\nconf_thres: 0.5\n";
    std::ofstream fout("/tmp/test.yaml");
    fout << yaml_content;
    fout.close();
    auto cfg = yolo::AppConfig::from_yaml("/tmp/test.yaml");
    EXPECT_EQ(cfg.source, "0");
    EXPECT_EQ(cfg.model.path, "models/test.onnx");
    EXPECT_FLOAT_EQ(cfg.conf_thres, 0.5f);
}
