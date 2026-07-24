#pragma once
#include <string>
#include <vector>
#include <optional>
#include <yaml-cpp/yaml.h>

namespace yolo {

struct ModelConfig {
    std::string path{"models/yolov8n.onnx"};
    std::string backend{"auto"};
    std::string task{"detect"};
};

struct TrackingConfig {
    bool enabled{true};
    std::string tracker{"iou"};
    float iou_threshold{0.3f};
    int max_age{30};
};

struct DrawConfig {
    bool labels{true};
    bool conf{true};
    bool track_id{true};
    bool center{false};
    bool box_coords{false};
    bool fps_overlay{true};
    int line_thickness{2};
    float font_scale{0.5f};
};

struct OutputConfig {
    bool show{true};
    std::optional<std::string> save_video;
    std::optional<std::string> log_path{"detections.jsonl"};
    std::string log_format{"jsonl"};
    bool log_per_frame{false};
    DrawConfig draw;
};

struct ReconnectConfig {
    bool enabled{true};
    int max_retries{100};
    float backoff_base{1.5f};
    float initial_delay{1.0f};
    float max_delay{30.0f};
    int timeout_ms{5000};
};

struct PipelineConfig {
    int queue_size{8};
    std::string drop_policy{"oldest"};
    int capture_fps{30};
    ReconnectConfig reconnect;
};

struct SecretsConfig {
    std::string env_user_var{"CAMERA_USER"};
    std::string env_pass_var{"CAMERA_PASSWORD"};
    std::optional<std::string> secrets_file;
};

struct AppConfig {
    std::string source{"0"};
    std::string source_type{"auto"};
    ModelConfig model;
    std::string device{"auto"};
    int imgsz{640};
    float conf_thres{0.35f};
    float iou_thres{0.45f};
    int max_det{300};
    std::vector<int> classes;
    bool half{false};
    int batch_size{1};
    int warmup{10};
    int frame_skip{0};
    std::optional<std::array<int,4>> roi;
    TrackingConfig tracking;
    OutputConfig output;
    PipelineConfig pipeline;
    SecretsConfig secrets;
    bool offline{false};
    bool verbose{false};

    static AppConfig from_yaml(const std::string& path);
    static AppConfig from_yaml_node(const YAML::Node& node);

    void apply_cli_overrides(const std::string& source_override,
                             const std::string& source_type_override,
                             const std::string& model_path_override,
                             const std::string& backend_override,
                             const std::string& device_override,
                             int imgsz_override,
                             float conf_override,
                             float iou_override);
};

std::string expand_source_with_secrets(const std::string& source, const SecretsConfig& secrets);
}
