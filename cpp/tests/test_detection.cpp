#include <gtest/gtest.h>
#include "yolo/core/detection.h"

TEST(DetectionTest, Clip) {
    yolo::BBox b{-10,-10,1000,1000};
    auto clipped = yolo::clip_bbox(b,640,480);
    EXPECT_EQ(clipped.x1, 0);
    EXPECT_EQ(clipped.y1, 0);
}

TEST(DetectionTest, IoU) {
    yolo::BBox a{0,0,10,10};
    yolo::BBox b{0,0,10,10};
    EXPECT_NEAR(yolo::iou(a,b), 1.0f, 1e-5);
    yolo::BBox c{20,20,30,30};
    EXPECT_NEAR(yolo::iou(a,c), 0.0f, 1e-5);
}

TEST(DetectionTest, Derived) {
    yolo::Detection det;
    det.bbox = {0,0,100,100};
    yolo::compute_derived(det,200,200);
    EXPECT_NEAR(det.xywh_norm[2], 0.5f, 1e-5);
    EXPECT_NEAR(det.area, 100*100, 1e-3);
}
