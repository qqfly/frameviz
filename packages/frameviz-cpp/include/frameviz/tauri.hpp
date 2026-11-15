/**
 * @file tauri.hpp
 * @brief Tauri Control Server communication for FrameViz C++ SDK
 *
 * Maintainer: qqfly
 * @date 2026-01-25
 * @bug No known bugs
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#ifndef FRAMEVIZ_CPP_TAURI_HPP
#define FRAMEVIZ_CPP_TAURI_HPP

#include <cstdint>
#include <optional>
#include <string>

namespace frameviz {

/**
 * @brief Get the Tauri control port from environment variable or default.
 *
 * Checks FRAMEVIZ_TAURI_CONTROL_PORT environment variable.
 * Defaults to 9528 if not set.
 *
 * @return Control port number.
 */
int32_t getTauriControlPort();

/**
 * @brief Try to request a new Tauri window from a running Tauri app.
 *
 * Sends a JSON command to the Tauri control server requesting a new window
 * with the specified view.
 *
 * @param view_id The view ID to display in the window.
 * @param title Window title.
 * @param width Window width in pixels.
 * @param height Window height in pixels.
 * @param x Optional window X position (screen coordinates).
 * @param y Optional window Y position (screen coordinates).
 * @param page Optional app-relative page path to open (e.g., "examples/...").
 * @param scene_id Optional scene_id to bind to.
 * @param performance_mode Optional performance mode ("performance", "balanced", "quality").
 * @param decorations Optional window decorations flag (true = show title bar, false = frameless).
 * @return true if the Tauri control server confirms success.
 */
bool tryOpenTauriWindow(
    const std::string &view_id,
    const std::string &title = "FrameViz",
    int32_t width = 800,
    int32_t height = 600,
    const std::optional<int32_t> &x = std::nullopt,
    const std::optional<int32_t> &y = std::nullopt,
    const std::string &page = "",
    const std::string &scene_id = "",
    const std::string &performance_mode = "balanced",
    bool decorations = true
);

/**
 * @brief Try to close a Tauri window by view ID.
 *
 * @param view_id The view ID whose window should be closed.
 * @return true if the Tauri control server confirms success.
 */
bool tryCloseTauriWindow(const std::string &view_id);

} // namespace frameviz

#endif // FRAMEVIZ_CPP_TAURI_HPP
