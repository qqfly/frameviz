#include <frameviz/business_auth.hpp>
/**
 * @file ui_server.cpp
 * @brief WebSocket server for UI commands implementation
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#include "urdf_robot/ui_server.hpp"
#include <ixwebsocket/IXWebSocketServer.h>
#include <nlohmann/json.hpp>
#include <algorithm>
#include <iostream>

using json = nlohmann::json;

namespace urdf_robot {

UIServer::UIServer(int port) : port_(port) {
    server_ = std::make_unique<ix::WebSocketServer>(port, "127.0.0.1");
}

UIServer::~UIServer() {
    stop();
}

void UIServer::onJointUpdate(JointUpdateCallback callback) {
    std::lock_guard<std::mutex> lock(callback_mutex_);
    joint_callback_ = std::move(callback);
}

void UIServer::onViewIdsUpdate(ViewIdsUpdateCallback callback) {
    std::lock_guard<std::mutex> lock(callback_mutex_);
    view_ids_callback_ = std::move(callback);
}

bool UIServer::start() {
    if (running_.load()) {
        return true;
    }

    // Set up connection handler
    server_->setOnClientMessageCallback(
        [this](std::shared_ptr<ix::ConnectionState> connectionState,
               ix::WebSocket& webSocket,
               const ix::WebSocketMessagePtr& msg) {
                if (!business_auth_.accept(webSocket, msg)) return;
            if (msg->type == ix::WebSocketMessageType::Open) {
                std::cout << "[UIServer] Client connected from "
                          << connectionState->getRemoteIp() << std::endl;

                // Store client reference
                {
                    std::lock_guard<std::mutex> lock(clients_mutex_);
                    // Clean up dead connections
                    clients_.erase(
                        std::remove_if(clients_.begin(), clients_.end(),
                            [](const std::weak_ptr<ix::WebSocket>& wp) {
                                return wp.expired();
                            }),
                        clients_.end());
                    // Note: We can't easily get shared_ptr from WebSocket& here
                    // The broadcast will handle sending to all clients via server
                }
            } else if (msg->type == ix::WebSocketMessageType::Close) {
                std::cout << "[UIServer] Client disconnected" << std::endl;
            } else if (msg->type == ix::WebSocketMessageType::Message) {
                handleMessage(nullptr, msg->str);
            } else if (msg->type == ix::WebSocketMessageType::Error) {
                std::cerr << "[UIServer] Error: " << msg->errorInfo.reason << std::endl;
            }
        }
    );

    // Start server
    auto res = server_->listen();
    if (!res.first) {
        std::cerr << "[UIServer] Failed to listen on port " << port_
                  << ": " << res.second << std::endl;
        return false;
    }

    server_->start();
    running_.store(true);
    std::cout << "[UIServer] Listening on ws://127.0.0.1:" << port_ << std::endl;

    return true;
}

void UIServer::stop() {
    if (!running_.load()) {
        return;
    }

    running_.store(false);
    server_->stop();
    std::cout << "[UIServer] Stopped" << std::endl;
}

void UIServer::wait() {
    server_->wait();
}

void UIServer::handleMessage(std::shared_ptr<ix::WebSocket> /*ws*/, const std::string& message) {
    try {
        auto payload = json::parse(message);
        std::string name = payload.value("name", "");
        auto args = payload.value("args", json::object());

        if (name == "set_joints") {
            auto positions = args.value("positions", std::vector<double>{});
            if (positions.size() == 6) {
                JointAngles angles;
                for (size_t i = 0; i < 6; ++i) {
                    angles[i] = positions[i];
                }

                // Call callback
                {
                    std::lock_guard<std::mutex> lock(callback_mutex_);
                    if (joint_callback_) {
                        joint_callback_(angles);
                    }
                }
            }
        } else if (name == "home") {
            JointAngles home_angles;
            home_angles.fill(0.0);

            // Call callback
            {
                std::lock_guard<std::mutex> lock(callback_mutex_);
                if (joint_callback_) {
                    joint_callback_(home_angles);
                }
            }
            std::cout << "[UIServer] Robot moved to home position" << std::endl;
        } else if (name == "set_view_ids") {
            std::optional<std::string> main_view_id;
            std::optional<std::string> collision_view_id;
            if (args.contains("main_view_id") && args["main_view_id"].is_string()) {
                main_view_id = args["main_view_id"].get<std::string>();
            }
            if (args.contains("collision_view_id") && args["collision_view_id"].is_string()) {
                collision_view_id = args["collision_view_id"].get<std::string>();
            }
            {
                std::lock_guard<std::mutex> lock(callback_mutex_);
                if (view_ids_callback_) {
                    view_ids_callback_(main_view_id, collision_view_id);
                }
            }
        } else if (name == "start_welding") {
            std::cout << "[UIServer] Start welding (not implemented)" << std::endl;
        } else if (name == "stop") {
            std::cout << "[UIServer] Stop (not implemented)" << std::endl;
        }
    } catch (const json::exception& e) {
        std::cerr << "[UIServer] JSON parse error: " << e.what() << std::endl;
    }
}

void UIServer::broadcastState(const JointAngles& angles) {
    json update;
    update["type"] = "state_update";
    update["joint_positions"] = std::vector<double>(angles.begin(), angles.end());

    std::string message = update.dump();

    // Broadcast to all connected clients
    for (auto& client : server_->getClients()) {
        if (business_auth_.authorized(client.get())) client->send(message);
    }
}

} // namespace urdf_robot
