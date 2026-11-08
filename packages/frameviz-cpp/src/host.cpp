/**
 * @file host.cpp
 * @brief FrameViz Host lifecycle management implementation
 *
 * Maintainer: qqfly
 * @date 2026-02-08
 * @bug No known bugs
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#include "frameviz/host.hpp"
#include "frameviz/types.hpp"
#include <nlohmann/json.hpp>
#include <fstream>
#include "frameviz/tauri.hpp"

#include <array>
#include <chrono>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#if defined(_WIN32) || defined(_WIN64)
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment(lib, "ws2_32.lib")
#include <windows.h>
#else
#include <arpa/inet.h>
#include <dirent.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

namespace frameviz {

namespace {

// ─────────────────────────────────────────────────────────────────────────────
// Process state
// ─────────────────────────────────────────────────────────────────────────────

#if !defined(_WIN32) && !defined(_WIN64)
static pid_t g_host_pid = 0;
#else
static HANDLE g_host_handle = nullptr;
#endif
static bool g_atexit_registered = false;

// ─────────────────────────────────────────────────────────────────────────────
// URL parsing
// ─────────────────────────────────────────────────────────────────────────────

struct HostPort {
  std::string host;
  int port;
};

HostPort parseWsUrl(const std::string &url) {
  // Extract host and port from "ws://host:port/..."
  HostPort result{"127.0.0.1", 9527};

  size_t start = 0;
  if (url.rfind("ws://", 0) == 0) {
    start = 5;
  } else if (url.rfind("wss://", 0) == 0) {
    start = 6;
  }

  std::string hostport = url.substr(start);
  size_t slash = hostport.find('/');
  if (slash != std::string::npos) {
    hostport = hostport.substr(0, slash);
  }

  size_t colon = hostport.rfind(':');
  if (colon != std::string::npos) {
    result.host = hostport.substr(0, colon);
    try {
      result.port = std::stoi(hostport.substr(colon + 1));
    } catch (...) {
      result.port = 9527;
    }
  } else {
    result.host = hostport;
  }

  if (result.host.empty()) {
    result.host = "127.0.0.1";
  }
  return result;
}

// ─────────────────────────────────────────────────────────────────────────────
// TCP check
// ─────────────────────────────────────────────────────────────────────────────

bool tcpConnect(const std::string &host, int port, double timeout_sec) {
#if defined(_WIN32) || defined(_WIN64)
  WSADATA wsa_data;
  WSAStartup(MAKEWORD(2, 2), &wsa_data);
  SOCKET sock = ::socket(AF_INET, SOCK_STREAM, 0);
  if (sock == INVALID_SOCKET) {
    return false;
  }

  u_long mode = 1;
  ioctlsocket(sock, FIONBIO, &mode);

  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(static_cast<u_short>(port));
  inet_pton(AF_INET, host.c_str(), &addr.sin_addr);

  ::connect(sock, reinterpret_cast<sockaddr *>(&addr), sizeof(addr));

  fd_set wset;
  FD_ZERO(&wset);
  FD_SET(sock, &wset);
  timeval tv{};
  tv.tv_sec = static_cast<long>(timeout_sec);
  tv.tv_usec = static_cast<long>((timeout_sec - tv.tv_sec) * 1e6);

  int sel = select(0, nullptr, &wset, nullptr, &tv);
  closesocket(sock);
  WSACleanup();
  return sel > 0;
#else
  int sock = ::socket(AF_INET, SOCK_STREAM, 0);
  if (sock < 0) {
    return false;
  }

  // Set non-blocking
  int flags = fcntl(sock, F_GETFL, 0);
  fcntl(sock, F_SETFL, flags | O_NONBLOCK);

  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(static_cast<uint16_t>(port));
  inet_pton(AF_INET, host.c_str(), &addr.sin_addr);

  int ret = ::connect(sock, reinterpret_cast<sockaddr *>(&addr), sizeof(addr));
  if (ret == 0) {
    close(sock);
    return true;
  }

  if (errno != EINPROGRESS) {
    close(sock);
    return false;
  }

  fd_set wset;
  FD_ZERO(&wset);
  FD_SET(sock, &wset);
  timeval tv{};
  tv.tv_sec = static_cast<long>(timeout_sec);
  tv.tv_usec = static_cast<long>((timeout_sec - tv.tv_sec) * 1e6);

  int sel = select(sock + 1, nullptr, &wset, nullptr, &tv);
  if (sel <= 0) {
    close(sock);
    return false;
  }

  int err = 0;
  socklen_t len = sizeof(err);
  getsockopt(sock, SOL_SOCKET, SO_ERROR, &err, &len);
  close(sock);
  return err == 0;
#endif
}

// ─────────────────────────────────────────────────────────────────────────────
// Filesystem helpers
// ─────────────────────────────────────────────────────────────────────────────

bool fileExists(const std::string &path) {
#if defined(_WIN32) || defined(_WIN64)
  DWORD attr = GetFileAttributesA(path.c_str());
  return attr != INVALID_FILE_ATTRIBUTES;
#else
  struct stat st{};
  return stat(path.c_str(), &st) == 0;
#endif
}

bool isExecutable(const std::string &path) {
#if defined(_WIN32) || defined(_WIN64)
  return fileExists(path);
#else
  return access(path.c_str(), X_OK) == 0;
#endif
}

bool dirExists(const std::string &path) {
#if defined(_WIN32) || defined(_WIN64)
  DWORD attr = GetFileAttributesA(path.c_str());
  return attr != INVALID_FILE_ATTRIBUTES && (attr & FILE_ATTRIBUTE_DIRECTORY);
#else
  struct stat st{};
  return stat(path.c_str(), &st) == 0 && S_ISDIR(st.st_mode);
#endif
}

std::string getHome() {
#if defined(_WIN32) || defined(_WIN64)
  const char *home = std::getenv("USERPROFILE");
  return home ? std::string(home) : "";
#else
  const char *home = std::getenv("HOME");
  return home ? std::string(home) : "";
#endif
}

std::optional<std::string> whichExecutable(const std::string &name) {
  const char *path_env = std::getenv("PATH");
  if (!path_env) {
    return std::nullopt;
  }
  std::string path_str(path_env);
#if defined(_WIN32) || defined(_WIN64)
  const char delim = ';';
#else
  const char delim = ':';
#endif
  size_t start = 0;
  while (start < path_str.size()) {
    size_t end = path_str.find(delim, start);
    if (end == std::string::npos) {
      end = path_str.size();
    }
    std::string dir = path_str.substr(start, end - start);
    if (!dir.empty()) {
      std::string candidate = dir + "/" + name;
      if (isExecutable(candidate)) {
        return candidate;
      }
    }
    start = end + 1;
  }
  return std::nullopt;
}

// ─────────────────────────────────────────────────────────────────────────────
// Repo root detection (mirrors Python _get_repo_root)
// ─────────────────────────────────────────────────────────────────────────────

bool looksLikeRepoRoot(const std::string &path) {
  if (!fileExists(path + "/pnpm-workspace.yaml") ||
      !dirExists(path + "/packages/frameviz-host-tauri")) return false;
  try {
    std::ifstream file(path + "/version.json");
    auto manifest = nlohmann::json::parse(file);
    return manifest.is_object() &&
           manifest.value("project_id", std::string{}) == "qqfly.frameviz" &&
           manifest.value("protocol_version", std::string{}) == PROTOCOL_VERSION;
  } catch (const std::exception &) {
    return false;
  }
}

std::string parentDir(const std::string &path) {
  size_t pos = path.rfind('/');
#if defined(_WIN32) || defined(_WIN64)
  size_t pos2 = path.rfind('\\');
  if (pos2 != std::string::npos && (pos == std::string::npos || pos2 > pos)) {
    pos = pos2;
  }
#endif
  if (pos == std::string::npos || pos == 0) {
    return "";
  }
  return path.substr(0, pos);
}

std::optional<std::string> getRepoRoot() {
  // Walk up from cwd
  std::array<char, 4096> buf{};
#if defined(_WIN32) || defined(_WIN64)
  if (GetCurrentDirectoryA(static_cast<DWORD>(buf.size()), buf.data()) == 0) {
    return std::nullopt;
  }
#else
  if (getcwd(buf.data(), buf.size()) == nullptr) {
    return std::nullopt;
  }
#endif
  std::string current(buf.data());
  for (int i = 0; i < 10; ++i) {
    if (current.empty()) {
      break;
    }
    if (looksLikeRepoRoot(current)) {
      return current;
    }
    std::string parent = parentDir(current);
    if (parent == current) {
      break;
    }
    current = parent;
  }
  return std::nullopt;
}

// ─────────────────────────────────────────────────────────────────────────────
// Executable search candidates
// ─────────────────────────────────────────────────────────────────────────────

void addIfExecutable(std::vector<std::string> &out, const std::string &path) {
  if (isExecutable(path)) {
    out.push_back(path);
  }
}

std::vector<std::string> getCandidates() {
  std::vector<std::string> candidates;
  auto repo_root = getRepoRoot();
  std::string home = getHome();

  // 1. FRAMEVIZ_HOST_PATH env
  const char *env_path = std::getenv("FRAMEVIZ_HOST_PATH");
  if (env_path && *env_path) {
    addIfExecutable(candidates, env_path);
  }

  // 2. FRAMEVIZ_TAURI_APP env
  const char *tauri_app = std::getenv("FRAMEVIZ_TAURI_APP");
  if (tauri_app && *tauri_app) {
    std::string tauri_app_str(tauri_app);
#ifdef __APPLE__
    // If it's an .app bundle, resolve to inner binary
    if (tauri_app_str.size() > 4 &&
        tauri_app_str.substr(tauri_app_str.size() - 4) == ".app") {
      std::string inner = tauri_app_str + "/Contents/MacOS/FrameViz";
      addIfExecutable(candidates, inner);
      addIfExecutable(candidates, tauri_app_str + "/Contents/MacOS/frameviz");
    } else {
      addIfExecutable(candidates, tauri_app_str);
    }
#else
    addIfExecutable(candidates, tauri_app_str);
#endif
  }

  // Only an explicit host path or this source tree may be auto-started.
#ifdef __APPLE__
  // 4. macOS .app bundles
  auto addAppBundle = [&](const std::string &app_path) {
    std::string inner = app_path + "/Contents/MacOS/FrameViz";
    addIfExecutable(candidates, inner);
    addIfExecutable(candidates, app_path + "/Contents/MacOS/frameviz");
  };

  if (repo_root) {
    addAppBundle(*repo_root +
                 "/packages/frameviz-host-tauri/src-tauri/target/release/"
                 "bundle/macos/FrameViz.app");
    addAppBundle(*repo_root +
                 "/packages/frameviz-host-tauri/src-tauri/target/debug/"
                 "bundle/macos/FrameViz.app");
  }
#endif

  // 5. Tauri exec candidates (non-.app)
  if (repo_root) {
#if defined(_WIN32) || defined(_WIN64)
    addIfExecutable(candidates,
                    *repo_root +
                        "/packages/frameviz-host-tauri/src-tauri/target/"
                        "release/frameviz.exe");
    addIfExecutable(candidates,
                    *repo_root +
                        "/packages/frameviz-host-tauri/src-tauri/target/"
                        "debug/frameviz.exe");
#else
    addIfExecutable(candidates,
                    *repo_root +
                        "/packages/frameviz-host-tauri/src-tauri/target/"
                        "release/frameviz");
    addIfExecutable(candidates,
                    *repo_root +
                        "/packages/frameviz-host-tauri/src-tauri/target/"
                        "debug/frameviz");
#endif
  }

  // 6. Linux AppImage candidates (mirrors Python _get_appimage_candidates)
#if !defined(_WIN32) && !defined(_WIN64) && !defined(__APPLE__)
  if (repo_root) {
    std::string appimage_dir =
        *repo_root +
        "/packages/frameviz-host-tauri/src-tauri/target/release/bundle/appimage";
    if (dirExists(appimage_dir)) {
      // Scan directory for FrameViz*.AppImage files
      DIR *dir = opendir(appimage_dir.c_str());
      if (dir) {
        struct dirent *entry;
        while ((entry = readdir(dir)) != nullptr) {
          std::string name(entry->d_name);
          if (name.size() > 9 && name.substr(0, 9) == "FrameViz" &&
              name.size() > 9 &&
              name.substr(name.size() - 9) == ".AppImage") {
            addIfExecutable(candidates, appimage_dir + "/" + name);
          }
        }
        closedir(dir);
      }
    }
  }

#endif

  return candidates;
}

// ─────────────────────────────────────────────────────────────────────────────
// Process management (Unix)
// ─────────────────────────────────────────────────────────────────────────────

#if !defined(_WIN32) && !defined(_WIN64)

void registerAtexit();

void launchHost(const std::string &exe, const std::vector<std::string> &args) {
  pid_t pid = fork();
  if (pid < 0) {
    throw std::runtime_error("fork() failed");
  }
  if (pid == 0) {
    // Child: redirect stdout/stderr to /dev/null
    int devnull = open("/dev/null", O_WRONLY);
    if (devnull >= 0) {
      dup2(devnull, STDOUT_FILENO);
      dup2(devnull, STDERR_FILENO);
      close(devnull);
    }

    // Build argv
    std::vector<const char *> c_args;
    c_args.push_back(exe.c_str());
    for (const auto &a : args) {
      c_args.push_back(a.c_str());
    }
    c_args.push_back(nullptr);

    execvp(exe.c_str(), const_cast<char *const *>(c_args.data()));
    // execvp only returns on failure
    _exit(127);
  }

  // Parent
  g_host_pid = pid;
  registerAtexit();
}

bool isHostProcessAlive() {
  if (g_host_pid <= 0) {
    return false;
  }
  int status = 0;
  pid_t ret = waitpid(g_host_pid, &status, WNOHANG);
  if (ret == 0) {
    return true;  // Still running
  }
  g_host_pid = 0;
  return false;
}

void killHostProcess() {
  if (g_host_pid <= 0) {
    return;
  }
  pid_t pid = g_host_pid;
  g_host_pid = 0;

  kill(pid, SIGTERM);

  // Wait up to 3 seconds for graceful exit
  for (int i = 0; i < 30; ++i) {
    int status = 0;
    pid_t ret = waitpid(pid, &status, WNOHANG);
    if (ret != 0) {
      return;  // Exited
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
  }

  // Force kill
  kill(pid, SIGKILL);
  waitpid(pid, nullptr, 0);
}

#else  // Windows

void registerAtexit();

void launchHost(const std::string &exe, const std::vector<std::string> &args) {
  std::string cmdline = "\"" + exe + "\"";
  for (const auto &a : args) {
    cmdline += " \"" + a + "\"";
  }

  STARTUPINFOA si{};
  si.cb = sizeof(si);
  si.dwFlags = STARTF_USESTDHANDLES;
  si.hStdInput = INVALID_HANDLE_VALUE;
  si.hStdOutput = INVALID_HANDLE_VALUE;
  si.hStdError = INVALID_HANDLE_VALUE;

  PROCESS_INFORMATION pi{};
  BOOL ok = CreateProcessA(nullptr, &cmdline[0], nullptr, nullptr, FALSE,
                           CREATE_NO_WINDOW, nullptr, nullptr, &si, &pi);
  if (!ok) {
    throw std::runtime_error("CreateProcess failed for " + exe);
  }

  CloseHandle(pi.hThread);
  g_host_handle = pi.hProcess;
  registerAtexit();
}

bool isHostProcessAlive() {
  if (!g_host_handle) {
    return false;
  }
  DWORD code = 0;
  if (GetExitCodeProcess(g_host_handle, &code) && code == STILL_ACTIVE) {
    return true;
  }
  CloseHandle(g_host_handle);
  g_host_handle = nullptr;
  return false;
}

void killHostProcess() {
  if (!g_host_handle) {
    return;
  }
  TerminateProcess(g_host_handle, 1);
  WaitForSingleObject(g_host_handle, 3000);
  CloseHandle(g_host_handle);
  g_host_handle = nullptr;
}

#endif

void registerAtexit() {
  if (g_atexit_registered) {
    return;
  }
  g_atexit_registered = true;
  std::atexit([]() { frameviz::stopHost(); });
}

// ─────────────────────────────────────────────────────────────────────────────
// Wait for port
// ─────────────────────────────────────────────────────────────────────────────

bool waitForReady(const std::string &host, int port, double timeout_sec) {
  auto deadline = std::chrono::steady_clock::now() +
                  std::chrono::milliseconds(static_cast<int>(timeout_sec * 1000));
  while (std::chrono::steady_clock::now() < deadline) {
    if (!isHostProcessAlive()) {
      return false;  // Process died during startup
    }
    if (tcpConnect(host, port, 0.2)) {
      return true;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
  }
  return false;
}

}  // namespace

// ═══════════════════════════════════════════════════════════════════════════════
// Public API
// ═══════════════════════════════════════════════════════════════════════════════

bool isHostRunning(const std::string &ws_url, double timeout_sec) {
  auto hp = parseWsUrl(ws_url);
  return tcpConnect(hp.host, hp.port, timeout_sec);
}

std::optional<std::string> findHostExecutable() {
  auto candidates = getCandidates();
  if (candidates.empty()) {
    return std::nullopt;
  }
  return candidates.front();
}

void startHost(const std::string &ws_url, double timeout_sec, bool headless) {
  if (isHostRunning(ws_url)) {
    return;
  }

  auto exe = findHostExecutable();
  if (!exe) {
    throw std::runtime_error(
        "FrameViz Host executable not found. "
        "Set FRAMEVIZ_HOST_PATH or FRAMEVIZ_TAURI_APP, "
        "install the FrameViz app, "
        "or build the Tauri host from the repository.");
  }

  auto hp = parseWsUrl(ws_url);
  std::vector<std::string> args = {"--ws-port", std::to_string(hp.port)};
  if (headless) {
    args.emplace_back("--headless");
  }

  std::cout << "[FrameViz] Starting host: " << *exe << " --ws-port " << hp.port
            << (headless ? " --headless" : "") << std::endl;

  launchHost(*exe, args);

  if (!waitForReady(hp.host, hp.port, timeout_sec)) {
    killHostProcess();
    throw std::runtime_error(
        "FrameViz Host started but did not become ready within " +
        std::to_string(static_cast<int>(timeout_sec)) + "s");
  }

  // Also wait for the Tauri control port so that tryOpenTauriWindow() works
  // immediately after startHost() returns.
  if (!headless) {
    int control_port = getTauriControlPort();
    waitForReady(hp.host, control_port, std::min(timeout_sec, 5.0));
  }

  std::cout << "[FrameViz] Host is ready: " << ws_url << std::endl;
}

void ensureHostRunning(const std::string &ws_url, double timeout_sec,
                       bool headless) {
  if (isHostRunning(ws_url)) {
    return;
  }
  startHost(ws_url, timeout_sec, headless);
}

void stopHost() {
  killHostProcess();
}

}  // namespace frameviz
