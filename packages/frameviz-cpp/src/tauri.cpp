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
  // Ensure Winsock is initialized
  getWinsockInitializer();

  int32_t port = getTauriControlPort();

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

  // Serialize to JSON
  std::string message;
  try {
    if (const char* token = std::getenv("FRAMEVIZ_AUTH_TOKEN")) payload["token"] = token;
    else if (auto token = getTokenFromDiscovery()) payload["token"] = *token;
    message = payload.dump();
  } catch (const json::exception &e) {
    std::cerr << "[FrameViz] Failed to serialize Tauri command: " << e.what()
              << std::endl;
    return false;
  }

  message += "\n";  // Add newline delimiter

  // Create socket
#ifdef _WIN32
  SOCKET sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
  if (sock == INVALID_SOCKET) {
    return false;
  }
#else
  int sock = socket(AF_INET, SOCK_STREAM, 0);
  if (sock < 0) {
    return false;
  }
#endif

  // Set non-blocking mode with timeout
#ifdef _WIN32
  DWORD timeout = 400;  // 400ms timeout
  setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&timeout, sizeof(timeout));
  setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, (const char*)&timeout, sizeof(timeout));
#else
  struct timeval tv;
  tv.tv_sec = 0;
  tv.tv_usec = 400000;  // 400ms timeout
  setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
  setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
#endif

  // Connect to control server
  struct sockaddr_in addr;
  addr.sin_family = AF_INET;
  addr.sin_port = htons(port);
  addr.sin_addr.s_addr = inet_addr("127.0.0.1");

#ifdef _WIN32
  if (connect(sock, (struct sockaddr*)&addr, sizeof(addr)) == SOCKET_ERROR) {
    closesocket(sock);
    return false;
  }
#else
  if (connect(sock, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
    close(sock);
    return false;
  }
#endif

  // Send command
  if (send(sock, message.c_str(), message.length(), 0) < 0) {
#ifdef _WIN32
    closesocket(sock);
#else
    close(sock);
#endif
    return false;
  }

  // Receive response (wait for newline)
  std::string response;
  char buffer[4096];
  bool newline_found = false;

  while (!newline_found) {
#ifdef _WIN32
    int bytes_received = recv(sock, buffer, sizeof(buffer) - 1, 0);
    if (bytes_received <= 0) {
      break;
    }
#else
    ssize_t bytes_received = recv(sock, buffer, sizeof(buffer) - 1, 0);
    if (bytes_received <= 0) {
      break;
    }
#endif
    buffer[bytes_received] = '\0';
    response += buffer;

    // Check for newline
    if (response.find('\n') != std::string::npos) {
      newline_found = true;
    }
  }

#ifdef _WIN32
  closesocket(sock);
#else
  close(sock);
#endif

  // Parse response
  if (!response.empty()) {
    try {
      json resp = json::parse(response);
      if (resp.contains("ok") && resp["ok"].is_boolean()) {
        return resp["ok"];
      }
    } catch (const json::exception &) {
      // Ignore parse errors
    }
  }

  // If we got here, connection succeeded but response parsing failed
  // Assume success if we could send the command
  return true;
}

bool tryCloseTauriWindow(const std::string &view_id) {
  // Ensure Winsock is initialized
  getWinsockInitializer();

  int32_t port = getTauriControlPort();

  // Build JSON payload
  json payload = {
    {"action", "close_view"},
    {"view_id", view_id}
  };

  std::string message;
  try {
    if (const char* token = std::getenv("FRAMEVIZ_AUTH_TOKEN")) payload["token"] = token;
    else if (auto token = getTokenFromDiscovery()) payload["token"] = *token;
    message = payload.dump();
  } catch (const json::exception &e) {
    return false;
  }

  message += "\n";

  // Create and connect socket (same as tryOpenTauriWindow)
#ifdef _WIN32
  SOCKET sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
  if (sock == INVALID_SOCKET) {
    return false;
  }
#else
  int sock = socket(AF_INET, SOCK_STREAM, 0);
  if (sock < 0) {
    return false;
  }
#endif

#ifdef _WIN32
  DWORD timeout = 400;
  setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&timeout, sizeof(timeout));
  setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, (const char*)&timeout, sizeof(timeout));
#else
  struct timeval tv;
  tv.tv_sec = 0;
  tv.tv_usec = 400000;
  setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
  setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
#endif

  struct sockaddr_in addr;
  addr.sin_family = AF_INET;
  addr.sin_port = htons(port);
  addr.sin_addr.s_addr = inet_addr("127.0.0.1");

#ifdef _WIN32
  if (connect(sock, (struct sockaddr*)&addr, sizeof(addr)) == SOCKET_ERROR) {
    closesocket(sock);
    return false;
  }
#else
  if (connect(sock, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
    close(sock);
    return false;
  }
#endif

  send(sock, message.c_str(), message.length(), 0);

#ifdef _WIN32
  closesocket(sock);
#else
  close(sock);
#endif

  return true;
}

} // namespace frameviz
