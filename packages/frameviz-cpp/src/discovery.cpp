/**
 * @file discovery.cpp
 * @brief Discovery file utilities implementation
 *
 * Maintainer: qqfly
 * @date 2026-01-25
 * @bug No known bugs
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#include "frameviz/discovery.hpp"
#include "frameviz/protocol_version.hpp"
#include <stdexcept>

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <nlohmann/json.hpp>
#include <optional>

#if defined(_WIN32) || defined(_WIN64)
#include <shlobj.h>
#include <windows.h>
#else
#include <pwd.h>
#include <sys/types.h>
#include <unistd.h>
#endif

namespace frameviz {

using json = nlohmann::json;

namespace {

std::string trimTrailingSlashes(std::string value) {
  while (!value.empty() && value.back() == '/') {
    value.pop_back();
  }
  return value;
}

std::string toLower(std::string value) {
  std::transform(value.begin(), value.end(), value.begin(),
                 [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
  return value;
}

bool isDefaultLocalWsUrl(const std::string &url) {
  std::string trimmed = trimTrailingSlashes(url);
  std::string lower = toLower(trimmed);
  const std::string ws_prefix = "ws://";
  const std::string wss_prefix = "wss://";

  size_t start = std::string::npos;
  if (lower.rfind(ws_prefix, 0) == 0) {
    start = ws_prefix.size();
  } else if (lower.rfind(wss_prefix, 0) == 0) {
    start = wss_prefix.size();
  } else {
    return false;
  }

  std::string hostport = lower.substr(start);
  size_t slash_pos = hostport.find('/');
  if (slash_pos != std::string::npos) {
    hostport = hostport.substr(0, slash_pos);
  }

  return hostport == "127.0.0.1:9527" || hostport == "localhost:9527";
}

} // namespace

std::optional<std::string> getDiscoveryPath() {
#if defined(_WIN32)
  if (const auto *value = _wgetenv(L"FRAMEVIZ_DISCOVERY_PATH"); value && *value) {
    return std::filesystem::path(value).u8string();
  }
  if (const auto *base = _wgetenv(L"FRAMEVIZ_HOME"); base && *base) {
    return (std::filesystem::path(base) / L"host.json").u8string();
  }
  for (const wchar_t *key : {L"LOCALAPPDATA", L"APPDATA"}) {
    if (const auto *base = _wgetenv(key); base && *base) {
      return (std::filesystem::path(base) / L"qqfly" / L"FrameViz" / L"host.json").u8string();
    }
  }
  return std::nullopt;
#else
  // Check environment variable first
  const char *env_path = std::getenv("FRAMEVIZ_DISCOVERY_PATH");
  if (env_path != nullptr && std::string(env_path).length() > 0) {
    return std::string(env_path);
  }

  if (const char *base = std::getenv("FRAMEVIZ_HOME")) {
    if (std::string(base).length()) return trimTrailingSlashes(base) + "/host.json";
  }
  // macOS and Linux: ~/.local/share/qqfly/frameviz/host.json
  const char *home = std::getenv("HOME");
  if (home != nullptr) {
    std::string path = std::string(home) + "/.local/share/qqfly/frameviz/host.json";
    return path;
  }

  // Fallback: getpwuid for systems without HOME env
#ifdef __unix__
  struct passwd *pw = getpwuid(getuid());
  if (pw != nullptr && pw->pw_dir != nullptr) {
    std::string path = std::string(pw->pw_dir) + "/.local/share/qqfly/frameviz/host.json";
    return path;
  }
#endif
  return std::nullopt;
#endif
}

std::optional<DiscoveryInfo> readDiscoveryFile(const std::string &path) {
  std::string actual_path = path;

  // Use default path if not specified
  if (actual_path.empty()) {
    auto default_path = getDiscoveryPath();
    if (!default_path.has_value()) {
      return std::nullopt;
    }
    actual_path = *default_path;
  }

  // Try to open and read the file
  std::ifstream file(std::filesystem::u8path(actual_path));
  if (!file.is_open()) {
    return std::nullopt;
  }

  try {
    // Parse JSON
    json data;
    file >> data;

    if (!data.is_object()) {
      return std::nullopt;
    }

    // Extract fields
    DiscoveryInfo info;

    // WebSocket URL (try "ws_url" first, then "url" for backward compatibility)
    if (data.contains("ws_url") && data["ws_url"].is_string()) {
      info.ws_url = data["ws_url"].get<std::string>();
    } else if (data.contains("url") && data["url"].is_string()) {
      info.ws_url = data["url"].get<std::string>();
    }

    // Token
    if (data.contains("token") && data["token"].is_string()) {
      info.token = data["token"].get<std::string>();
    }

    // Viewer URL (for browser mode)
    if (data.contains("viewer_url") && data["viewer_url"].is_string()) {
      info.viewer_url = data["viewer_url"].get<std::string>();
    }

    // Port
    if (data.contains("port") && data["port"].is_number_integer()) {
      info.port = data["port"].get<int32_t>();
    }

    // Version
    if (data.contains("version") && data["version"].is_string()) {
      info.version = data["version"].get<std::string>();
    }
    if (data.contains("pid") && data["pid"].is_number_unsigned() &&
        data["pid"].get<uint64_t>() <= std::numeric_limits<uint32_t>::max()) {
      info.pid = data["pid"].get<uint32_t>();
    }

    return info;

  } catch (const json::exception &e) {
    std::cerr << "[FrameViz] Failed to parse discovery file: " << e.what()
              << std::endl;
    return std::nullopt;
  } catch (const std::exception &e) {
    std::cerr << "[FrameViz] Error reading discovery file: " << e.what()
              << std::endl;
    return std::nullopt;
  }
}

std::optional<std::string> getWsUrlFromDiscovery() {
  auto info = readDiscoveryFile();
  if (info.has_value() && !info->ws_url.empty()) {
    return info->ws_url;
  }
  return std::nullopt;
}

std::optional<std::string> getTokenFromDiscovery() {
  auto info = readDiscoveryFile();
  if (info.has_value() && !info->token.empty()) {
    return info->token;
  }
  return std::nullopt;
}

std::optional<int32_t> getPortFromDiscovery() {
  auto info = readDiscoveryFile();
  if (info.has_value() && info->port > 0) {
    return info->port;
  }
  return std::nullopt;
}

std::optional<std::string> getViewerUrlFromDiscovery() {
  auto info = readDiscoveryFile();
  if (info.has_value() && !info->viewer_url.empty()) {
    return info->viewer_url;
  }
  return std::nullopt;
}

std::string resolveWsUrl(const std::string &url) {
  if (url.empty() || isDefaultLocalWsUrl(url)) {
    auto discovered = getWsUrlFromDiscovery();
    if (discovered.has_value() && !discovered->empty()) {
      auto info = readDiscoveryFile();
      if (info && !isProtocolCompatible(info->version)) throw std::runtime_error(hostVersionError(info->version));
      return *discovered;
    }
  }

  if (!url.empty()) {
    return url;
  }

  return "ws://127.0.0.1:9527";
}

} // namespace frameviz
