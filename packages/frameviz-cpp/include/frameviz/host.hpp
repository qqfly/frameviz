/**
 * @file host.hpp
 * @brief FrameViz Host lifecycle management for C++ SDK
 *
 * Provides utilities to detect, locate, and auto-start the FrameViz Host
 * application.  Mirrors the Python SDK's frameviz.host module.
 *
 * Maintainer: qqfly
 * @date 2026-02-08
 * @bug No known bugs
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#ifndef FRAMEVIZ_CPP_HOST_HPP
#define FRAMEVIZ_CPP_HOST_HPP

#include <optional>
#include <string>

namespace frameviz {

/**
 * @brief Check whether a FrameViz Host is reachable at the given WebSocket URL.
 *
 * Performs a quick TCP connect to the host/port extracted from @p ws_url.
 *
 * @param ws_url  WebSocket URL (default: ws://127.0.0.1:9527).
 * @param timeout_sec  TCP connect timeout in seconds (default: 0.2).
 * @return true if the port is open and accepting connections.
 */
bool isHostRunning(const std::string &ws_url = "ws://127.0.0.1:9527",
                   double timeout_sec = 0.2);

/**
 * @brief Locate the FrameViz Host executable on the local filesystem.
 *
 * Search order:
 *  1. `FRAMEVIZ_HOST_PATH` environment variable
 *  2. `FRAMEVIZ_TAURI_APP` environment variable
 *  3. Executables built inside a matching qqfly.frameviz source tree
 *     (project identity and protocol version must match)
 *  4. Linux AppImage bundles in that source tree
 *
 * Global PATH/system app names are not searched automatically.
 *
 * @return Absolute path to the executable, or std::nullopt if not found.
 */
std::optional<std::string> findHostExecutable();

/**
 * @brief Launch the FrameViz Host and wait until its WebSocket port is ready.
 *
 * If the host is already running, this is a no-op that returns immediately.
 *
 * @param ws_url   Target WebSocket URL (default: ws://127.0.0.1:9527).
 * @param timeout_sec  Max seconds to wait for the host to become ready.
 * @param headless Launch in headless mode (no GUI window).
 * @throws std::runtime_error if the executable cannot be found or startup
 *         times out.
 */
void startHost(const std::string &ws_url = "ws://127.0.0.1:9527",
               double timeout_sec = 10.0,
               bool headless = false);

/**
 * @brief Ensure a FrameViz Host is running, starting one if necessary.
 *
 * Equivalent to:
 * @code
 *   if (!isHostRunning(ws_url)) startHost(ws_url, timeout_sec, headless);
 * @endcode
 *
 * @param ws_url   Target WebSocket URL.
 * @param timeout_sec  Startup timeout.
 * @param headless Launch in headless mode.
 */
void ensureHostRunning(const std::string &ws_url = "ws://127.0.0.1:9527",
                       double timeout_sec = 10.0,
                       bool headless = false);

/**
 * @brief Stop the host process if it was started by this module.
 *
 * Sends SIGTERM, waits briefly, then SIGKILL if still running.
 * Called automatically via atexit when startHost() succeeds.
 */
void stopHost();

} // namespace frameviz

#endif // FRAMEVIZ_CPP_HOST_HPP
