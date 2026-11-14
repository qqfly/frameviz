#include "frameviz/discovery.hpp"
/**
 * @file tauri.cpp
 * @brief Tauri Control Server communication implementation
 *
 * Maintainer: qqfly
 * @date 2026-01-25
 * @bug No known bugs
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#include "frameviz/tauri.hpp"

#include <chrono>
#include <cstdlib>
#include <iostream>
#include <nlohmann/json.hpp>
#include <optional>

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment(lib, "ws2_32.lib")
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>
#endif

namespace frameviz {

using json = nlohmann::json;

namespace {
// Initialize Winsock on Windows
class WinsockInitializer {
public:
  WinsockInitializer() {
#ifdef _WIN32
    WSADATA wsa_data;
    if (WSAStartup(MAKEWORD(2, 2), &wsa_data) != 0) {
      std::cerr << "[FrameViz] WSAStartup failed" << std::endl;
    }
#endif
  }

  ~WinsockInitializer() {
#ifdef _WIN32
    WSACleanup();
#endif
  }
};

// Global initializer (runs on first use)
WinsockInitializer &getWinsockInitializer() {
  static WinsockInitializer initializer;
  return initializer;
}
#ifdef _WIN32
using ControlSocket = SOCKET;
constexpr ControlSocket invalidSocket = INVALID_SOCKET;
#else
using ControlSocket = int;
constexpr ControlSocket invalidSocket = -1;
#endif

bool exchangeControlMessage(ControlSocket sock, const std::string &message) {
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(getTauriControlPort());
  addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  if (connect(sock, reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) != 0) return false;

  // Creating or closing a native WebView can take longer than one UI frame.
#ifdef _WIN32
  const DWORD timeout = 2000;
#else
  const timeval timeout{2, 0};
#endif
  setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char *>(&timeout), sizeof(timeout));
  setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char *>(&timeout), sizeof(timeout));
#if defined(SO_NOSIGPIPE)
  const int enabled = 1;
  setsockopt(sock, SOL_SOCKET, SO_NOSIGPIPE, &enabled, sizeof(enabled));
#endif
#ifdef MSG_NOSIGNAL
  constexpr int sendFlags = MSG_NOSIGNAL;
#else
  constexpr int sendFlags = 0;
#endif
  for (size_t offset = 0; offset < message.size();) {
    const auto sent = send(sock, message.data() + offset,
                           static_cast<int>(message.size() - offset), sendFlags);
    if (sent <= 0) return false;
    offset += sent;
  }

  std::string response;
  char buffer[1024];
  while (response.size() < 16384) {
    const auto received = recv(sock, buffer, sizeof(buffer), 0);
    if (received <= 0) return false;
    response.append(buffer, received);
    const auto newline = response.find('\n');
    if (newline == std::string::npos) continue;
    const auto reply = json::parse(response.substr(0, newline), nullptr, false);
    return reply.is_object() && reply.contains("ok") && reply["ok"] == true;
  }
  return false;
}

bool requestWindow(json payload) {
  getWinsockInitializer();
  if (const char *token = std::getenv("FRAMEVIZ_AUTH_TOKEN")) payload["token"] = token;
  else if (auto token = getTokenFromDiscovery()) payload["token"] = *token;
  const auto sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
  if (sock == invalidSocket) return false;

  bool ok = false;
  try {
    ok = exchangeControlMessage(sock, payload.dump() + '\n');
  } catch (const json::exception &) {
    // Treat an invalid request or response as a failed operation.
  }
#ifdef _WIN32
  closesocket(sock);
#else
  close(sock);
#endif
  return ok;
}

} // namespace

int32_t getTauriControlPort() {
  // Ensure Winsock is initialized
  getWinsockInitializer();

  // Check environment variable
  const char *env_port = std::getenv("FRAMEVIZ_TAURI_CONTROL_PORT");
  if (env_port != nullptr) {
    try {
      return std::stoi(env_port);
    } catch (...) {
      // Invalid port, use default
    }
  }

  // Default port
  return 9528;
}

bool tryOpenTauriWindow(
    const std::string &view_id,
    const std::string &title,
    int32_t width,
    int32_t height,
    const std::optional<int32_t> &x,
    const std::optional<int32_t> &y,
    const std::string &page,
    const std::string &scene_id,
    const std::string &performance_mode,
    bool decorations
) {
  // Build JSON payload
  json payload = {
    {"action", "open_view"},
    {"view_id", view_id},
    {"title", title},
    {"width", width},
    {"height", height},
    {"decorations", decorations}
  };

  if (x.has_value()) {
    payload["x"] = *x;
  }
  if (y.has_value()) {
    payload["y"] = *y;
  }
  if (!page.empty()) {
    payload["page"] = page;
  }
  if (!scene_id.empty()) {
    payload["scene_id"] = scene_id;
  }
  if (!performance_mode.empty()) {
    payload["performance_mode"] = performance_mode;
  }

  return requestWindow(std::move(payload));
}

bool tryCloseTauriWindow(const std::string &view_id) {
  return requestWindow({{"action", "close_view"}, {"view_id", view_id}});
}

} // namespace frameviz
