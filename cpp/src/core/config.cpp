#include "yolo/core/config.h"
#include "yolo/core/common.h"
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <spdlog/spdlog.h>

namespace yolo {

static std::string get_env(const std::string& var) {
    const char* v = std::getenv(var.c_str());
    return v ? std::string(v) : "";
}

std::string expand_source_with_secrets(const std::string& source, const SecretsConfig& secrets) {
    if (source.empty()) return source;
    std::string out = source;
    std::string user = get_env(secrets.env_user_var);
    std::string pwd = get_env(secrets.env_pass_var);
    // secrets file
    std::string file_user, file_pwd;
    if (secrets.secrets_file) {
        try {
            YAML::Node node = YAML::LoadFile(*secrets.secrets_file);
            if (node["rtsp_user"]) file_user = node["rtsp_user"].as<std::string>();
            else if (node["user"]) file_user = node["user"].as<std::string>();
            if (node["rtsp_password"]) file_pwd = node["rtsp_password"].as<std::string>();
            else if (node["password"]) file_pwd = node["password"].as<std::string>();
        } catch (...) {}
    }
    if (!file_user.empty()) user = file_user;
    if (!file_pwd.empty()) pwd = file_pwd;

    // replace placeholders
    auto replace_all = [](std::string& s, const std::string& from, const std::string& to){
        size_t pos=0;
        while((pos=s.find(from,pos))!=std::string::npos){ s.replace(pos, from.length(), to); pos+=to.length(); }
    };
    if (!user.empty()) replace_all(out, "CAMERA_USER", user);
    if (!pwd.empty()) replace_all(out, "CAMERA_PASSWORD", pwd);

    // if rtsp and no @ and we have credentials, inject
    if (out.rfind("rtsp://",0)==0) {
        auto at_start = out.find("://");
        if (at_start!=std::string::npos) {
            auto slash = out.find('/', at_start+3);
            std::string host_part = (slash==std::string::npos)? out.substr(at_start+3) : out.substr(at_start+3, slash-(at_start+3));
            if (host_part.find('@')==std::string::npos && !user.empty() && !pwd.empty()) {
                std::string rest = out.substr(at_start+3);
                out = "rtsp://" + user + ":" + pwd + "@" + rest;
            }
        }
    }
    return out;
}

template<typename T>
static T get_or(const YAML::Node& n, const std::string& key, T def) {
    if (n[key]) {
        try { return n[key].as<T>(); } catch(...) { return def; }
    }
    return def;
}

AppConfig AppConfig::from_yaml_node(const YAML::Node& node) {
    AppConfig cfg;
    if (node["source"]) cfg.source = node["source"].as<std::string>();
    if (node["source_type"]) cfg.source_type = node["source_type"].as<std::string>();
    if (node["model"]) {
        auto m = node["model"];
        if (m["path"]) cfg.model.path = m["path"].as<std::string>();
        if (m["backend"]) cfg.model.backend = m["backend"].as<std::string>();
        if (m["task"]) cfg.model.task = m["task"].as<std::string>();
    }
    cfg.device = get_or<std::string>(node, "device", cfg.device);
    cfg.imgsz = get_or<int>(node, "imgsz", cfg.imgsz);
    cfg.conf_thres = get_or<float>(node, "conf_thres", cfg.conf_thres);
    cfg.iou_thres = get_or<float>(node, "iou_thres", cfg.iou_thres);
    cfg.max_det = get_or<int>(node, "max_det", cfg.max_det);
    if (node["classes"]) cfg.classes = node["classes"].as<std::vector<int>>();
    cfg.half = get_or<bool>(node, "half", cfg.half);
    cfg.frame_skip = get_or<int>(node, "frame_skip", cfg.frame_skip);

    if (node["tracking"]) {
        auto t = node["tracking"];
        cfg.tracking.enabled = get_or<bool>(t, "enabled", cfg.tracking.enabled);
        cfg.tracking.tracker = get_or<std::string>(t, "tracker", cfg.tracking.tracker);
        cfg.tracking.iou_threshold = get_or<float>(t, "iou_threshold", cfg.tracking.iou_threshold);
        cfg.tracking.max_age = get_or<int>(t, "max_age", cfg.tracking.max_age);
    }
    if (node["output"]) {
        auto o = node["output"];
        cfg.output.show = get_or<bool>(o, "show", cfg.output.show);
        if (o["save_video"]) cfg.output.save_video = o["save_video"].as<std::string>();
        if (o["log_path"]) cfg.output.log_path = o["log_path"].as<std::string>();
        cfg.output.log_format = get_or<std::string>(o, "log_format", cfg.output.log_format);
        cfg.output.log_per_frame = get_or<bool>(o, "log_per_frame", cfg.output.log_per_frame);
        if (o["draw"]) {
            auto d = o["draw"];
            cfg.output.draw.labels = get_or<bool>(d, "labels", cfg.output.draw.labels);
            cfg.output.draw.conf = get_or<bool>(d, "conf", cfg.output.draw.conf);
            cfg.output.draw.track_id = get_or<bool>(d, "track_id", cfg.output.draw.track_id);
            cfg.output.draw.center = get_or<bool>(d, "center", cfg.output.draw.center);
            cfg.output.draw.box_coords = get_or<bool>(d, "box_coords", cfg.output.draw.box_coords);
            cfg.output.draw.fps_overlay = get_or<bool>(d, "fps_overlay", cfg.output.draw.fps_overlay);
            cfg.output.draw.line_thickness = get_or<int>(d, "line_thickness", cfg.output.draw.line_thickness);
            cfg.output.draw.font_scale = get_or<float>(d, "font_scale", cfg.output.draw.font_scale);
        }
    }
    if (node["pipeline"]) {
        auto p = node["pipeline"];
        cfg.pipeline.queue_size = get_or<int>(p, "queue_size", cfg.pipeline.queue_size);
        cfg.pipeline.drop_policy = get_or<std::string>(p, "drop_policy", cfg.pipeline.drop_policy);
        cfg.pipeline.capture_fps = get_or<int>(p, "capture_fps", cfg.pipeline.capture_fps);
        if (p["reconnect"]) {
            auto r = p["reconnect"];
            cfg.pipeline.reconnect.enabled = get_or<bool>(r, "enabled", cfg.pipeline.reconnect.enabled);
            cfg.pipeline.reconnect.max_retries = get_or<int>(r, "max_retries", cfg.pipeline.reconnect.max_retries);
            cfg.pipeline.reconnect.backoff_base = get_or<float>(r, "backoff_base", cfg.pipeline.reconnect.backoff_base);
            cfg.pipeline.reconnect.initial_delay = get_or<float>(r, "initial_delay", cfg.pipeline.reconnect.initial_delay);
            cfg.pipeline.reconnect.max_delay = get_or<float>(r, "max_delay", cfg.pipeline.reconnect.max_delay);
            cfg.pipeline.reconnect.timeout_ms = get_or<int>(r, "timeout_ms", cfg.pipeline.reconnect.timeout_ms);
        }
    }
    if (node["secrets"]) {
        auto s = node["secrets"];
        cfg.secrets.env_user_var = get_or<std::string>(s, "env_user_var", cfg.secrets.env_user_var);
        cfg.secrets.env_pass_var = get_or<std::string>(s, "env_pass_var", cfg.secrets.env_pass_var);
        if (s["secrets_file"]) cfg.secrets.secrets_file = s["secrets_file"].as<std::string>();
    }
    cfg.offline = get_or<bool>(node, "offline", cfg.offline);
    cfg.verbose = get_or<bool>(node, "verbose", cfg.verbose);
    return cfg;
}

AppConfig AppConfig::from_yaml(const std::string& path) {
    YAML::Node node = YAML::LoadFile(path);
    return from_yaml_node(node);
}

}
