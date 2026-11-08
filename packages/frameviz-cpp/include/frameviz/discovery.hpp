/**
 * @file discovery.hpp
 * @brief Discovery file utilities for FrameViz C++ SDK
 *
 * Maintainer: qqfly
 * @date 2026-01-25
 * @bug No known bugs
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#ifndef FRAMEVIZ_CPP_DISCOVERY_HPP
#define FRAMEVIZ_CPP_DISCOVERY_HPP

#include <cstdint>
#include <optional>
#include <string>

namespace frameviz {

/**
 * @brief Get the platform-specific path for the discovery file (host.json).
 *
 * Priority:
 * 1. FRAMEVIZ_DISCOVERY_PATH environment variable (if set)
 * 2. Platform-specific default:
 *    - macOS: ~/.local/share/qqfly/frameviz/host.json
 *    - Linux: ~/.local/share/qqfly/frameviz/host.json
 *    - Windows: %LOCALAPPDATA%/qqfly/FrameViz/host.json
 *
 * @return Path to host.json, or empty std::optional if unable to determine.
 */
std::optional<std::string> getDiscoveryPath();

/**
 * @brief Structure to hold parsed discovery file data.
 */
struct DiscoveryInfo {
  std::string ws_url;      ///< WebSocket URL (e.g., "ws://127.0.0.1:9527")
  std::string viewer_url;  ///< Viewer URL (e.g., "http://127.0.0.1:8080/")
  std::string token;       ///< Authentication token
  int32_t port = 0;        ///< Port number (0 means unavailable)
  std::string version;     ///< Protocol version
};

/**
 * @brief Read and parse the discovery file.
 *
 * @param path Optional explicit path. If empty, uses getDiscoveryPath().
 * @return Parsed DiscoveryInfo, or empty std::optional if file doesn't exist
 *         or is invalid.
 */
std::optional<DiscoveryInfo> readDiscoveryFile(
    const std::string &path = "");

/**
 * @brief Get WebSocket URL from discovery file.
 *
 * @return WebSocket URL string, or empty std::optional if not available.
 */
std::optional<std::string> getWsUrlFromDiscovery();

/**
 * @brief Get authentication token from discovery file.
 *
 * @return Token string, or empty std::optional if not available.
 */
std::optional<std::string> getTokenFromDiscovery();

/**
 * @brief Get port number from discovery file.
 *
 * @return Port number, or empty std::optional if not available.
 */
std::optional<int32_t> getPortFromDiscovery();

/**
 * @brief Get viewer URL from discovery file (for browser mode).
 *
 * @return Viewer URL string, or empty std::optional if not available.
 */
std::optional<std::string> getViewerUrlFromDiscovery();

/**
 * @brief Resolve WebSocket URL, preferring discovery when appropriate.
 *
 * Behavior:
 * - If url is empty or a default local URL, try discovery.
 * - If discovery is available, return the discovered ws_url.
 * - Otherwise, return the provided url or the default local URL.
 *
 * @param url Optional URL (e.g., "ws://127.0.0.1:9527")
 * @return Resolved WebSocket URL string
 */
std::string resolveWsUrl(const std::string &url);

} // namespace frameviz

#endif // FRAMEVIZ_CPP_DISCOVERY_HPP
