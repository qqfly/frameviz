/**
 * @file asset_server.hpp
 * @brief HTTP server for serving mesh assets with CORS
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#ifndef URDF_ROBOT_ASSET_SERVER_HPP
#define URDF_ROBOT_ASSET_SERVER_HPP

#include <atomic>
#include <memory>
#include <string>
#include <thread>
#include <filesystem>

namespace urdf_robot {

/**
 * @brief HTTP server for serving static mesh files with CORS headers.
 *
 * Serves files from a root directory on a specified port, adding
 * CORS headers to allow cross-origin requests from the viewer.
 */
class AssetServer {
public:
    /**
     * @brief Construct an asset server.
     * @param root_dir Root directory to serve files from
     * @param port HTTP port (default: 8081)
     */
    AssetServer(const std::filesystem::path& root_dir, int port = 8081);

    /**
     * @brief Destructor - stops the server.
     */
    ~AssetServer();

    // Non-copyable, non-movable
    AssetServer(const AssetServer&) = delete;
    AssetServer& operator=(const AssetServer&) = delete;

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
     * @brief Check if server is running.
     */
    bool isRunning() const { return running_.load(); }

    /**
     * @brief Get the base URL for this server.
     * @return URL like "http://localhost:8081"
     */
    std::string baseUrl() const;

    /**
     * @brief Get the server port.
     */
    int port() const { return port_; }

    /**
     * @brief Get the root directory.
     */
    const std::filesystem::path& rootDir() const { return root_dir_; }

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;

    std::filesystem::path root_dir_;
    int port_;
    std::atomic<bool> running_{false};
    std::thread server_thread_;
};

} // namespace urdf_robot

#endif // URDF_ROBOT_ASSET_SERVER_HPP
