/**
 * @file asset_server.cpp
 * @brief HTTP asset server implementation
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#include "urdf_robot/asset_server.hpp"

// IMPORTANT: Ensure OpenSSL support is completely disabled for cpp-httplib
// The library uses #ifdef, so we must #undef to disable it
#ifdef CPPHTTPLIB_OPENSSL_SUPPORT
#undef CPPHTTPLIB_OPENSSL_SUPPORT
#endif

#include "httplib.h"

#include <iostream>
#include <regex>
#include <set>
#include <algorithm>

namespace urdf_robot {

struct AssetServer::Impl {
    httplib::Server server;
};

AssetServer::AssetServer(const std::filesystem::path& root_dir, int port)
    : impl_(std::make_unique<Impl>()), root_dir_(root_dir), port_(port) {
}

AssetServer::~AssetServer() {
    stop();
}

bool AssetServer::start() {
    if (running_.load()) {
        return true;
    }

    if (!std::filesystem::exists(root_dir_)) {
        std::cerr << "[AssetServer] Root directory does not exist: " << root_dir_ << std::endl;
        return false;
    }

    std::error_code root_error;
    root_dir_ = std::filesystem::weakly_canonical(root_dir_, root_error);
    if (root_error) return false;
    auto local_origin = [](const std::string& value) {
        return value.empty() || std::regex_match(value, std::regex(R"((http|https|tauri)://(localhost|127\.0\.0\.1|\[::1\]|tauri\.localhost)(:[0-9]+)?)"));
    };
    impl_->server.set_pre_routing_handler([this, local_origin](const httplib::Request& req, httplib::Response& res) {
        if (!local_origin(req.get_header_value("Origin"))) {
            res.status = 403; return httplib::Server::HandlerResponse::Handled;
        }
        if (req.method != "GET" && req.method != "HEAD" && req.method != "OPTIONS") {
            res.status = 405; return httplib::Server::HandlerResponse::Handled;
        }
        std::filesystem::path requested(req.path);
        bool hidden = req.path.find('\0') != std::string::npos;
        for (const auto& part : requested) {
            const auto name = part.string();
            if (!name.empty() && name[0] == '.') hidden = true;
        }
        std::error_code ec;
        const auto candidate = std::filesystem::weakly_canonical(root_dir_ / requested.relative_path(), ec);
        const auto relative = candidate.lexically_relative(root_dir_);
        std::string ext = candidate.extension().string();
        std::transform(ext.begin(), ext.end(), ext.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
        const std::set<std::string> allowed = {".stl", ".dae", ".obj", ".mtl", ".urdf", ".png", ".jpg", ".jpeg"};
        if (hidden || ec || relative.empty() || relative.is_absolute() || *relative.begin() == ".." ||
            !std::filesystem::is_regular_file(candidate, ec) || ec || !allowed.count(ext)) {
            res.status = 404; return httplib::Server::HandlerResponse::Handled;
        }
        return httplib::Server::HandlerResponse::Unhandled;
    });
    impl_->server.set_post_routing_handler([local_origin](const httplib::Request& req, httplib::Response& res) {
        const auto origin = req.get_header_value("Origin");
        if (!origin.empty() && local_origin(origin)) {
            res.set_header("Access-Control-Allow-Origin", origin);
            res.set_header("Vary", "Origin");
        }
        res.set_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS");
    });
    impl_->server.Options(".*", [](const httplib::Request&, httplib::Response& res) { res.status = 204; });

    // Mount the root directory for static file serving
    auto ret = impl_->server.set_mount_point("/", root_dir_.string());
    if (!ret) {
        std::cerr << "[AssetServer] Failed to mount directory: " << root_dir_ << std::endl;
        return false;
    }

    // Start server in a separate thread
    server_thread_ = std::thread([this]() {
        std::cout << "[AssetServer] Starting on http://127.0.0.1:" << port_
                  << " (root: " << root_dir_ << ")" << std::endl;
        impl_->server.listen("127.0.0.1", port_);
    });

    // Wait a bit for server to start
    std::this_thread::sleep_for(std::chrono::milliseconds(100));

    if (!impl_->server.is_running()) {
        std::cerr << "[AssetServer] Failed to start on port " << port_ << std::endl;
        if (server_thread_.joinable()) {
            server_thread_.join();
        }
        return false;
    }

    running_.store(true);
    std::cout << "[AssetServer] Started on " << baseUrl() << std::endl;
    return true;
}

void AssetServer::stop() {
    if (!running_.load()) {
        return;
    }

    running_.store(false);
    impl_->server.stop();

    if (server_thread_.joinable()) {
        server_thread_.join();
    }

    std::cout << "[AssetServer] Stopped" << std::endl;
}

std::string AssetServer::baseUrl() const {
    return "http://localhost:" + std::to_string(port_);
}

} // namespace urdf_robot
