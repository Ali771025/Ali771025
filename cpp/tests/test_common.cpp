#include <gtest/gtest.h>
#include "yolo/core/common.h"

TEST(CommonTest, MaskUrl) {
    std::string url="rtsp://user:mypass@192.168.1.10:554/stream";
    std::string masked=yolo::mask_url(url);
    EXPECT_TRUE(masked.find("mypass")==std::string::npos);
    EXPECT_NE(masked.find("****"), std::string::npos);
}

TEST(CommonTest, GuessSource) {
    EXPECT_EQ(yolo::guess_source_type("0"), yolo::SourceType::USB);
    EXPECT_EQ(yolo::guess_source_type("rtsp://user:pass@ip/stream"), yolo::SourceType::RTSP);
}
