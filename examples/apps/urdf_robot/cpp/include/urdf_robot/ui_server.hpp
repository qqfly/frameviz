#include <frameviz/business_auth.hpp>
/**
 * @file ui_server.hpp
 * @brief WebSocket server for UI commands (joint control)
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#ifndef URDF_ROBOT_UI_SERVER_HPP
#define URDF_ROBOT_UI_SERVER_HPP

#include "types.hpp"
#include <atomic>
#include <functional>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <thread>
#include <vector>

// Forward declarations
namespace ix {
class WebSocketServer;
class WebSocket;
} // namespace ix

namespace urdf_robot {

/**
 * @brief WebSocket server for receiving UI commands.
 *
 * Listens on a specified port for commands from the UI:
 * - {"name": "set_joints", "args": {"positions": [6 floats]}}
 * - {"name": "home", "args": {}}
 * - {"name": "set_view_ids", "args": {"main_view_id": "v_x", "collision_view_id": "v_y"}}
 *
 * Broadcasts state updates to all connected clients:
 * - {"type": "state_update", "joint_positions": [6 floats]}
 */
class UIServer {
public:
    using JointUpdateCallback = std::function<void(const JointAngles&)>;
    using ViewIdsUpdateCallback = std::function<void(
        const std::optional<std::string>& main_view_id,
        const std::optional<std::string>& collision_view_id)>;

    /**
     * @brief Construct a UI server.
     * @param port WebSocket port (default: 9620)
     */
    explicit UIServer(int port = 9620);

    /**
     * @brief Destructor - stops the server.
     */
    ~UIServer();

    // Non-copyable, non-movable
    UIServer(const UIServer&) = delete;
    UIServer& operator=(const UIServer&) = delete;

    /**
     * @brief Set callback for joint updates.
     * @param callback Function to call when joints are updated
     */
    void onJointUpdate(JointUpdateCallback callback);
    void onViewIdsUpdate(ViewIdsUpdateCallback callback);

    /**
     * @brief Start the server (non-blocking).
     * @return true if started successfully
     */
    bool start();

    /**
     * @brief Stop the server.
     */
    void stop();

    /**
     * @brief Wait for server to stop (blocking).
     */
    void wait();

    /**
     * @brief Broadcast state update to all connected clients.
     * @param angles Current joint angles
     */
    void broadcastState(const JointAngles& angles);

    /**
     * @brief Check if server is running.
     */
    bool isRunning() const { return running_.load(); }

    /**
     * @brief Get the server port.
     */
    int port() const { return port_; }

private:
    void handleMessage(std::shared_ptr<ix::WebSocket> ws, const std::string& message);

    int port_;
    frameviz::BusinessAuth business_auth_;
    std::unique_ptr<ix::WebSocketServer> server_;
    std::atomic<bool> running_{false};
    std::thread server_thread_;

    JointUpdateCallback joint_callback_;
    ViewIdsUpdateCallback view_ids_callback_;
    std::mutex callback_mutex_;

    // Connected clients
    std::vector<std::weak_ptr<ix::WebSocket>> clients_;
    std::mutex clients_mutex_;
};

} // namespace urdf_robot

#endif // URDF_ROBOT_UI_SERVER_HPP
