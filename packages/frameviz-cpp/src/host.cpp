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
#include "frameviz/discovery.hpp"
#include "frameviz/internal/ws_url.hpp"
#include "frameviz/types.hpp"
#include "frameviz/protocol_version.hpp"
#include <nlohmann/json.hpp>
#include <fstream>
#include "frameviz/tauri.hpp"

#include <array>
#include <cerrno>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <string>
#include <string_view>
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
#include <spawn.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
extern char **environ;
#endif

#ifdef __APPLE__
#include <CoreFoundation/CoreFoundation.h>
#endif

namespace frameviz {

namespace {

// ─────────────────────────────────────────────────────────────────────────────
// Process state
// ─────────────────────────────────────────────────────────────────────────────

#if !defined(_WIN32) && !defined(_WIN64)
static pid_t g_host_pid = 0;
static int g_owner_pipe = -1;
#else
static HANDLE g_host_handle = nullptr;
static HANDLE g_owner_pipe = nullptr;
#endif
std::mutex host_mutex;

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
  const char *address = host == "localhost" ? "127.0.0.1" : host.c_str();
#if defined(_WIN32) || defined(_WIN64)
  WSADATA wsa_data;
  WSAStartup(MAKEWORD(2, 2), &wsa_data);
  SOCKET sock = ::socket(AF_INET, SOCK_STREAM, 0);
  if (sock == INVALID_SOCKET) {
    WSACleanup();
    return false;
  }

  u_long mode = 1;
  ioctlsocket(sock, FIONBIO, &mode);

  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(static_cast<u_short>(port));
  if (inet_pton(AF_INET, address, &addr.sin_addr) != 1) {
    closesocket(sock);
    WSACleanup();
    return false;
  }

  ::connect(sock, reinterpret_cast<sockaddr *>(&addr), sizeof(addr));

  fd_set wset;
  FD_ZERO(&wset);
  FD_SET(sock, &wset);
  timeval tv{};
  tv.tv_sec = static_cast<long>(timeout_sec);
  tv.tv_usec = static_cast<long>((timeout_sec - tv.tv_sec) * 1e6);

  int sel = select(0, nullptr, &wset, nullptr, &tv);
  int error = 0;
  int len = sizeof(error);
  const bool connected = sel > 0 &&
      getsockopt(sock, SOL_SOCKET, SO_ERROR, reinterpret_cast<char *>(&error), &len) == 0 &&
      error == 0;
  closesocket(sock);
  WSACleanup();
  return connected;
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
  if (inet_pton(AF_INET, address, &addr.sin_addr) != 1) {
    close(sock);
    return false;
  }

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
  std::error_code error;
  if (!std::filesystem::is_regular_file(std::filesystem::u8path(path), error)) return false;
#if defined(_WIN32) || defined(_WIN64)
  return true;
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
           isProtocolCompatible(manifest.value("protocol_version", std::string{}));
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

#ifdef _WIN32
std::optional<std::string> windowsAppVersion(const std::filesystem::path &path) {
  const auto size = GetFileVersionInfoSizeW(path.c_str(), nullptr);
  if (!size) return std::nullopt;
  std::vector<unsigned char> data(size);
  if (!GetFileVersionInfoW(path.c_str(), 0, size, data.data())) return std::nullopt;
  void *value = nullptr;
  UINT length = 0;
  if (!VerQueryValueW(data.data(), L"\\", &value, &length) ||
      length < sizeof(VS_FIXEDFILEINFO)) return std::nullopt;
  const auto &version = *static_cast<VS_FIXEDFILEINFO *>(value);
  if (version.dwSignature != VS_FFI_SIGNATURE) return std::nullopt;
  return std::to_string(HIWORD(version.dwProductVersionMS)) + "." +
         std::to_string(LOWORD(version.dwProductVersionMS)) + "." +
         std::to_string(HIWORD(version.dwProductVersionLS));
}

void addWindowsInstallations(std::vector<std::string> &out) {
  auto add = [&](const std::filesystem::path &directory) {
    if (!directory.is_absolute()) return;
    const auto executable = directory / L"frameviz.exe";
    if (auto version = windowsAppVersion(executable); version && isProtocolCompatible(*version)) {
      addIfExecutable(out, executable.u8string());
    }
  };
  constexpr wchar_t key[] = L"Software\\qqfly\\FrameViz";
  // Tauri MSI writes InstallDir. NSIS writes the default value of the same key.
  for (HKEY root : {HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE}) {
    for (DWORD view : {DWORD{0}, DWORD{RRF_SUBKEY_WOW6464KEY}, DWORD{RRF_SUBKEY_WOW6432KEY}}) {
      for (const wchar_t *name : {L"InstallDir", L""}) {
        std::vector<wchar_t> directory(32768);
        DWORD size = static_cast<DWORD>(directory.size() * sizeof(wchar_t));
        if (RegGetValueW(root, key, name, RRF_RT_REG_SZ | view,
                         nullptr, directory.data(), &size) == ERROR_SUCCESS) {
          add(directory.data());
        }
      }
    }
  }
  for (const wchar_t *key : {L"LOCALAPPDATA", L"ProgramW6432", L"ProgramFiles", L"ProgramFiles(x86)"}) {
    if (const auto *directory = _wgetenv(key); directory && *directory) {
      add(std::filesystem::path(directory) / L"FrameViz");
    }
  }
}
#endif

#ifdef __linux__
std::optional<std::string> linuxRuntimeVersion(const std::string &path) {
  if (!isExecutable(path)) return std::nullopt;
  int output[2];
  if (pipe2(output, O_CLOEXEC | O_NONBLOCK) != 0) return std::nullopt;
  posix_spawn_file_actions_t actions;
  if (posix_spawn_file_actions_init(&actions) != 0) {
    close(output[0]);
    close(output[1]);
    return std::nullopt;
  }
  const char *args[] = {path.c_str(), "--version", nullptr};
  pid_t pid = 0;
  const bool spawned =
      posix_spawn_file_actions_addopen(&actions, STDIN_FILENO, "/dev/null", O_RDONLY, 0) == 0 &&
      posix_spawn_file_actions_addopen(&actions, STDERR_FILENO, "/dev/null", O_WRONLY, 0) == 0 &&
      posix_spawn_file_actions_adddup2(&actions, output[1], STDOUT_FILENO) == 0 &&
      posix_spawn(&pid, path.c_str(), &actions, nullptr, const_cast<char **>(args), environ) == 0;
  posix_spawn_file_actions_destroy(&actions);
  close(output[1]);
  std::optional<std::string> version;
  if (spawned) {
    int status = 0;
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    pid_t result;
    do {
      result = waitpid(pid, &status, WNOHANG);
      if (result == 0) std::this_thread::sleep_for(std::chrono::milliseconds(10));
    } while ((result == 0 || (result < 0 && errno == EINTR)) &&
             std::chrono::steady_clock::now() < deadline);
    if (result == pid && WIFEXITED(status) && WEXITSTATUS(status) == 0) {
      std::array<char, 128> buffer{};
      const auto bytes = read(output[0], buffer.data(), buffer.size());
      constexpr std::string_view prefix = "FrameViz Host v";
      if (bytes > 0) {
        std::string outputText(buffer.data(), bytes);
        outputText.erase(outputText.find_last_not_of(" \r\n\t") + 1);
        if (outputText.compare(0, prefix.size(), prefix) == 0) {
          version = outputText.substr(prefix.size());
        }
      }
    } else if (result == 0 || (result < 0 && errno == EINTR)) {
      kill(pid, SIGKILL);
      while (waitpid(pid, nullptr, 0) < 0 && errno == EINTR) {}
    }
  }
  close(output[0]);
  return version;
}

void addLinuxInstallations(std::vector<std::string> &out) {
  auto add = [&](const std::string &executable) {
    if (auto version = linuxRuntimeVersion(executable); version && isProtocolCompatible(*version)) {
      out.push_back(executable);
    }
  };
  if (detail::hasDesktop()) add("/usr/bin/frameviz");
  add("/usr/bin/frameviz-server");
  add("/usr/local/bin/frameviz-server");
  if (const char *home = std::getenv("HOME"); home && *home) {
    add(std::string(home) + "/.local/bin/frameviz-server");
  }
}

int freeLocalPort() {
  const int socketFd = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
  if (socketFd < 0) throw std::runtime_error("Cannot allocate a local port for FrameViz");
  sockaddr_in address{};
  address.sin_family = AF_INET;
  address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  socklen_t length = sizeof(address);
  const bool bound = bind(socketFd, reinterpret_cast<sockaddr *>(&address), length) == 0 &&
                     getsockname(socketFd, reinterpret_cast<sockaddr *>(&address), &length) == 0;
  close(socketFd);
  if (!bound) throw std::runtime_error("Cannot allocate a local port for FrameViz");
  return ntohs(address.sin_port);
}
#endif

#ifdef __APPLE__
struct MacApp {
  std::string executable;
  std::string version;
};

std::optional<MacApp> readMacApp(const std::string &app) {
  const auto url = CFURLCreateFromFileSystemRepresentation(
      nullptr, reinterpret_cast<const UInt8 *>(app.data()), app.size(), true);
  if (!url) return std::nullopt;
  const auto info = CFBundleCopyInfoDictionaryForURL(url);
  CFRelease(url);
  if (!info) return std::nullopt;
  auto readString = [&](CFStringRef key) -> std::string {
    auto value = static_cast<CFStringRef>(CFDictionaryGetValue(info, key));
    std::array<char, 256> buffer{};
    if (!value || CFGetTypeID(value) != CFStringGetTypeID() ||
        !CFStringGetCString(value, buffer.data(), buffer.size(), kCFStringEncodingUTF8)) {
      return {};
    }
    return buffer.data();
  };
  const auto id = readString(CFSTR("CFBundleIdentifier"));
  const auto type = readString(CFSTR("CFBundlePackageType"));
  const auto name = readString(CFSTR("CFBundleExecutable"));
  const auto version = readString(CFSTR("CFBundleShortVersionString"));
  CFRelease(info);
  if (id != "dev.qqfly.frameviz.viewer" || type != "APPL" ||
      (name != "frameviz" && name != "FrameViz")) {
    return std::nullopt;
  }
  const auto directory = app + "/Contents/MacOS";
  const auto executable = directory + "/" + name;
  std::error_code error;
  const auto resolvedDirectory = std::filesystem::canonical(directory, error);
  if (error) return std::nullopt;
  const auto resolvedExecutable = std::filesystem::canonical(executable, error);
  if (error || resolvedExecutable.parent_path() != resolvedDirectory || !isExecutable(executable)) {
    return std::nullopt;
  }
  return MacApp{executable, version};
}
#endif

std::vector<std::string> getCandidates() {
  std::vector<std::string> candidates;
  auto repo_root = getRepoRoot();
#ifdef _WIN32
  addWindowsInstallations(candidates);
#elif defined(__linux__)
  addLinuxInstallations(candidates);
#endif
#ifdef __APPLE__
  auto addAppBundle = [&](const std::string &app_path) {
    if (auto app = readMacApp(app_path); app && isProtocolCompatible(app->version)) {
      candidates.push_back(app->executable);
    }
  };

  if (const char *home = std::getenv("HOME"); home && *home) {
    addAppBundle(std::string(home) + "/Applications/FrameViz.app");
  }
  addAppBundle("/Applications/FrameViz.app");
  if (repo_root) {
    addAppBundle(*repo_root +
                 "/packages/frameviz-host-tauri/src-tauri/target/release/"
                 "bundle/macos/FrameViz.app");
    addAppBundle(*repo_root +
                 "/packages/frameviz-host-tauri/src-tauri/target/debug/"
                 "bundle/macos/FrameViz.app");
  }
#endif

  // Tauri executables in a matching source tree.
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

  // Linux AppImages in a matching source tree.
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

void launchHost(const std::string &exe, const std::vector<std::string> &args) {
  // The Host sees EOF even if a signal prevents normal SDK teardown.
  int owner[2];
  if (pipe(owner) != 0) throw std::runtime_error("Cannot create FrameViz Host ownership pipe");
  if (fcntl(owner[0], F_SETFD, FD_CLOEXEC) < 0 ||
      fcntl(owner[1], F_SETFD, FD_CLOEXEC) < 0) {
    close(owner[0]);
    close(owner[1]);
    throw std::runtime_error("Cannot configure FrameViz Host ownership pipe");
  }
  // Prepare argv and env before fork: the caller may already have SDK threads.
  std::vector<const char *> argv{exe.c_str()};
  for (const auto &arg : args) argv.push_back(arg.c_str());
  argv.push_back(nullptr);
  std::vector<const char *> env;
  for (auto entry = environ; *entry; ++entry) {
    if (std::string_view(*entry).rfind("FRAMEVIZ_SDK_MANAGED=", 0) != 0) env.push_back(*entry);
  }
  env.push_back("FRAMEVIZ_SDK_MANAGED=1");
  env.push_back(nullptr);
  const auto argv_data = const_cast<char *const *>(argv.data());
  const auto env_data = const_cast<char *const *>(env.data());
  const auto executable = exe.c_str();
  const pid_t pid = fork();
  if (pid < 0) {
    close(owner[0]);
    close(owner[1]);
    throw std::runtime_error("Cannot fork FrameViz Host");
  }
  if (pid == 0) {
    close(owner[1]);
    // Put the App outside the example's foreground terminal process group.
    if (setsid() < 0 || dup2(owner[0], STDIN_FILENO) < 0 ||
        fcntl(STDIN_FILENO, F_SETFD, 0) < 0) _exit(126);
    if (owner[0] != STDIN_FILENO) close(owner[0]);
    const int devnull = open("/dev/null", O_WRONLY);
    if (devnull >= 0) {
      dup2(devnull, STDOUT_FILENO);
      dup2(devnull, STDERR_FILENO);
      if (devnull > STDERR_FILENO) close(devnull);
    }
    execve(executable, argv_data, env_data);
    _exit(127);
  }

  close(owner[0]);
  g_owner_pipe = owner[1];
  g_host_pid = pid;
}

void releaseHostPipe() {
  if (g_owner_pipe >= 0) close(g_owner_pipe);
  g_owner_pipe = -1;
}

uint32_t launchedHostPid() {
  return static_cast<uint32_t>(g_host_pid);
}

bool isHostProcessAlive() {
  if (g_host_pid <= 0) {
    return false;
  }
  int status = 0;
  pid_t ret = waitpid(g_host_pid, &status, WNOHANG);
  if (ret == 0 || (ret < 0 && errno == EINTR)) {
    return true;  // Still running
  }
  g_host_pid = 0;
  releaseHostPipe();
  return false;
}

void killHostProcess() {
  if (!isHostProcessAlive()) return;
  pid_t pid = g_host_pid;

  kill(pid, SIGTERM);

  // Wait up to 3 seconds for graceful exit
  for (int i = 0; i < 30; ++i) {
    if (!isHostProcessAlive()) return;
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
  }

  // Force kill
  kill(pid, SIGKILL);
  while (waitpid(pid, nullptr, 0) < 0 && errno == EINTR) {}
  g_host_pid = 0;
  releaseHostPipe();
}

#else  // Windows

void launchHost(const std::string &exe, const std::vector<std::string> &args) {
  const auto executable = std::filesystem::u8path(exe);
  std::wstring cmdline = L"\"" + executable.wstring() + L"\"";
  for (const auto &a : args) {
    cmdline += L" \"" + std::filesystem::u8path(a).wstring() + L"\"";
  }

  SECURITY_ATTRIBUTES security{sizeof(SECURITY_ATTRIBUTES), nullptr, TRUE};
  HANDLE input = nullptr, owner = nullptr;
  if (!CreatePipe(&input, &owner, &security, 0)) {
    throw std::runtime_error("Cannot create FrameViz Host ownership pipe");
  }
  const HANDLE output = CreateFileW(L"NUL", GENERIC_WRITE, FILE_SHARE_WRITE, &security,
                                    OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
  if (output == INVALID_HANDLE_VALUE || !SetHandleInformation(owner, HANDLE_FLAG_INHERIT, 0)) {
    CloseHandle(input);
    CloseHandle(owner);
    if (output != INVALID_HANDLE_VALUE) CloseHandle(output);
    throw std::runtime_error("Cannot configure FrameViz Host standard handles");
  }

  std::vector<wchar_t> environment;
  auto entries = GetEnvironmentStringsW();
  if (!entries) {
    CloseHandle(input);
    CloseHandle(owner);
    CloseHandle(output);
    throw std::runtime_error("Cannot read environment for FrameViz Host");
  }
  constexpr std::wstring_view managedKey = L"FRAMEVIZ_SDK_MANAGED=";
  for (const wchar_t *entry = entries; *entry;) {
    const std::wstring_view value(entry);
    if (_wcsnicmp(entry, managedKey.data(), managedKey.size()) != 0) {
      environment.insert(environment.end(), entry, entry + value.size() + 1);
    }
    entry += value.size() + 1;
  }
  FreeEnvironmentStringsW(entries);
  constexpr wchar_t managed[] = L"FRAMEVIZ_SDK_MANAGED=1";
  environment.insert(environment.end(), managed, managed + sizeof(managed));
  environment.push_back(L'\0');

  STARTUPINFOEXW startup{};
  startup.StartupInfo.cb = sizeof(startup);
  startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
  startup.StartupInfo.hStdInput = input;
  startup.StartupInfo.hStdOutput = output;
  startup.StartupInfo.hStdError = output;
  SIZE_T listSize = 0;
  InitializeProcThreadAttributeList(nullptr, 1, 0, &listSize);
  std::vector<char> attributes(listSize);
  startup.lpAttributeList = reinterpret_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(attributes.data());
  HANDLE handles[] = {input, output};
  PROCESS_INFORMATION pi{};
  BOOL ok = FALSE;
  if (InitializeProcThreadAttributeList(startup.lpAttributeList, 1, 0, &listSize)) {
    if (UpdateProcThreadAttribute(startup.lpAttributeList, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                                  handles, sizeof(handles), nullptr, nullptr)) {
      ok = CreateProcessW(executable.c_str(), cmdline.data(), nullptr, nullptr, TRUE,
                          CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP |
                              CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT,
                          environment.data(), nullptr, &startup.StartupInfo, &pi);
    }
    DeleteProcThreadAttributeList(startup.lpAttributeList);
  }
  CloseHandle(input);
  CloseHandle(output);
  if (!ok) {
    CloseHandle(owner);
    throw std::runtime_error("CreateProcess failed for " + exe);
  }

  CloseHandle(pi.hThread);
  g_host_handle = pi.hProcess;
  g_owner_pipe = owner;
}

void releaseHostPipe() {
  if (g_owner_pipe) CloseHandle(g_owner_pipe);
  g_owner_pipe = nullptr;
}

uint32_t launchedHostPid() {
  return g_host_handle ? GetProcessId(g_host_handle) : 0;
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
  releaseHostPipe();
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
  releaseHostPipe();
}

#endif

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

bool processExists(uint32_t pid) {
  if (!pid) return false;
#if defined(_WIN32) || defined(_WIN64)
  const HANDLE process = OpenProcess(SYNCHRONIZE, FALSE, pid);
  if (!process) return GetLastError() == ERROR_ACCESS_DENIED;
  const bool running = WaitForSingleObject(process, 0) == WAIT_TIMEOUT;
  CloseHandle(process);
  return running;
#else
  if (pid > static_cast<uint32_t>(std::numeric_limits<pid_t>::max())) return false;
  return kill(static_cast<pid_t>(pid), 0) == 0 || errno == EPERM;
#endif
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
#ifdef _WIN32
  for (const wchar_t *key : {L"FRAMEVIZ_HOST_PATH", L"FRAMEVIZ_TAURI_APP"}) {
    const auto *value = _wgetenv(key);
    if (!value || !*value) continue;
    const std::filesystem::path path(value);
    if (!isExecutable(path.u8string())) {
      throw std::runtime_error("Explicit FrameViz Host is not executable: " + path.u8string());
    }
    if (auto version = windowsAppVersion(path); version && !isProtocolCompatible(*version)) {
      throw std::runtime_error(path.u8string() + ": " + hostVersionError(*version));
    }
    return std::filesystem::absolute(path).u8string();
  }
#else
  for (const char *key : {"FRAMEVIZ_HOST_PATH", "FRAMEVIZ_TAURI_APP"}) {
    const char *value = std::getenv(key);
    if (!value || !*value) continue;
    const std::string path(value);
#ifdef __APPLE__
    if (std::filesystem::path(path).extension() == ".app") {
      auto app = readMacApp(path);
      if (!app) throw std::runtime_error(std::string(key) + " is not a valid FrameViz App: " + path);
      if (auto error = hostVersionError(app->version); !error.empty()) {
        throw std::runtime_error(std::string(key) + " (" + path + "): " + error);
      }
      return app->executable;
    }
#endif
    if (!isExecutable(path)) {
      throw std::runtime_error(std::string(key) + " is not an executable FrameViz Host: " + path);
    }
#ifdef __linux__
    if (auto version = linuxRuntimeVersion(path); version && !isProtocolCompatible(*version)) {
      throw std::runtime_error(std::string(key) + " (" + path + "): " + hostVersionError(*version));
    }
#endif
    return std::filesystem::absolute(path).string();
  }
#endif
  auto candidates = getCandidates();
  if (candidates.empty()) {
    return std::nullopt;
  }
  return candidates.front();
}

bool detail::isLocalWsUrl(const std::string &url) {
  static const std::regex local(R"(^ws://(127\.0\.0\.1|localhost)(:[0-9]+)?(/.*)?$)");
  return std::regex_match(url, local);
}

bool detail::hasDesktop() {
#ifdef __linux__
  const char *display = std::getenv("DISPLAY");
  const char *wayland = std::getenv("WAYLAND_DISPLAY");
  return (display && *display) || (wayland && *wayland);
#else
  return true;
#endif
}

std::optional<DiscoveryInfo> detail::runningLocalHost() {
  auto info = readDiscoveryFile();
  if (info && isLocalWsUrl(info->ws_url) && processExists(info->pid) &&
      isHostRunning(info->ws_url)) {
    return info;
  }
  return std::nullopt;
}

std::string detail::startLocalHost(const std::string &ws_url, double timeout_sec,
                                  bool headless, bool automaticEndpoint) {
  std::lock_guard<std::mutex> lock(host_mutex);
  if (!isLocalWsUrl(ws_url)) throw std::runtime_error("Only local FrameViz Hosts can be started");
  if (!automaticEndpoint && isHostRunning(ws_url)) {
    return ws_url;
  }
  if (auto host = runningLocalHost()) {
    if (auto error = hostVersionError(host->version); !error.empty()) throw std::runtime_error(error);
    if (!automaticEndpoint) throw std::runtime_error("The local discovery record belongs to a Host on a different port");
    return host->ws_url;
  }
  if (isHostProcessAlive()) {
    throw std::runtime_error("This process already started a FrameViz Host");
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
#ifdef __linux__
  if (automaticEndpoint && isHostRunning(ws_url) &&
      std::filesystem::path(*exe).filename() == "frameviz-server") {
    hp.port = freeLocalPort();
  }
#endif
  std::vector<std::string> args = {"--ws-port", std::to_string(hp.port)};
  if (headless) {
    args.emplace_back("--headless");
  }

  std::cout << "[FrameViz] Starting host: " << *exe << " --ws-port " << hp.port
            << (headless ? " --headless" : "") << std::endl;

  launchHost(*exe, args);

  const auto deadline = std::chrono::steady_clock::now() + std::chrono::duration<double>(timeout_sec);
  while (std::chrono::steady_clock::now() < deadline && isHostProcessAlive()) {
    if (auto info = readDiscoveryFile(); info && info->pid == launchedHostPid() &&
        !info->token.empty() && isLocalWsUrl(info->ws_url) && isHostRunning(info->ws_url)) {
      const auto error = hostVersionError(info->version);
      if (!error.empty() || (!automaticEndpoint && info->port != hp.port)) {
        killHostProcess();
        throw std::runtime_error(error.empty() ? "FrameViz Host did not bind the requested port" : error);
      }
      if (std::filesystem::path(*exe).filename() != "frameviz-server") {
        waitForReady("127.0.0.1", getTauriControlPort(), std::min(timeout_sec, 2.0));
      }
      std::cout << "[FrameViz] Host is ready: " << info->ws_url << std::endl;
      return info->ws_url;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(25));
  }
  killHostProcess();
  throw std::runtime_error(
      "FrameViz Host did not publish a ready discovery record within " +
      std::to_string(timeout_sec) + "s");
}

void startHost(const std::string &ws_url, double timeout_sec, bool headless) {
  detail::startLocalHost(ws_url, timeout_sec, headless, false);
}

void ensureHostRunning(const std::string &ws_url, double timeout_sec,
                       bool headless) {
  if (isHostRunning(ws_url)) {
    return;
  }
  startHost(ws_url, timeout_sec, headless);
}

void stopHost() {
  std::lock_guard<std::mutex> lock(host_mutex);
  killHostProcess();
}

}  // namespace frameviz
