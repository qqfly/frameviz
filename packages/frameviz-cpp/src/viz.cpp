#include <regex>
#if defined(_WIN32) || defined(_WIN64)
#include <windows.h>
#include <shellapi.h>
#else
#include <spawn.h>
#include <sys/wait.h>
extern char **environ;
#endif
/**
 * @file viz.cpp
 * @brief High-level FrameViz visualization API implementation
 *
 * Maintainer: qqfly
 * @date 2026-01-25
 * @bug No known bugs
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#include "frameviz/viz.hpp"
#include "frameviz/host.hpp"
#include "frameviz/internal/color_utils.hpp"
#include "frameviz/internal/ws_url.hpp"
#include "frameviz/tauri.hpp"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <thread>

namespace frameviz {
using detail::packColorsToU8;
using detail::validateColorComponents;

// ─────────────────────────────────────────────────────────────────────────────
// Helper functions
// ─────────────────────────────────────────────────────────────────────────────

namespace {

constexpr size_t kPointsChunkSize = 500000;

int getWsPortFromUrl(const std::string &url) {
  // Basic parsing for ws://host:port or wss://host:port forms.
  constexpr int kDefaultWsPort = 9527;
  const std::string scheme_sep = "://";
  size_t start = 0;
  size_t scheme_pos = url.find(scheme_sep);
  if (scheme_pos != std::string::npos) {
    start = scheme_pos + scheme_sep.size();
  }

  size_t path_pos = url.find('/', start);
  std::string hostport =
      (path_pos == std::string::npos) ? url.substr(start)
                                      : url.substr(start, path_pos - start);
  if (hostport.empty()) {
    return kDefaultWsPort;
  }

  // Handle IPv6 like [::1]:9527
  if (!hostport.empty() && hostport.front() == '[') {
    size_t end = hostport.find(']');
    if (end != std::string::npos && end + 1 < hostport.size() &&
        hostport[end + 1] == ':') {
      try {
        return std::stoi(hostport.substr(end + 2));
      } catch (...) {
        return kDefaultWsPort;
      }
    }
    return kDefaultWsPort;
  }

  size_t colon_pos = hostport.rfind(':');
  if (colon_pos == std::string::npos || colon_pos + 1 >= hostport.size()) {
    return kDefaultWsPort;
  }
  try {
    return std::stoi(hostport.substr(colon_pos + 1));
  } catch (...) {
    return kDefaultWsPort;
  }
}

std::string getViewerUrl() {
  auto discovered = getViewerUrlFromDiscovery();
  if (discovered.has_value() && !discovered->empty()) {
    return *discovered;
  }
  return "http://127.0.0.1:8080/";
}

void appendQueryParam(std::string &url, const std::string &key,
                      const std::string &value) {
  if (url.find('?') == std::string::npos) {
    url.push_back('?');
  } else if (!url.empty() && url.back() != '?' && url.back() != '&') {
    url.push_back('&');
  }
  url += key;
  url.push_back('=');
  url += value;
}

std::string buildViewerUrl(const std::string &viewer_url,
                           const std::string &view_id, int ws_port,
                           const std::string &performance_mode) {
  std::string full_url = viewer_url;
  appendQueryParam(full_url, "view_id", view_id);
  appendQueryParam(full_url, "ws_port", std::to_string(ws_port));
  appendQueryParam(full_url, "performance_mode", performance_mode);
  return full_url;
}

} // namespace

namespace {

json toList(const Vec3 &v) { return json::array({v[0], v[1], v[2]}); }

json normalizeQuat(const Quat &q) {
  float norm =
      std::sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]);
  if (norm < 1e-7f) {
    return json::array({0.0f, 0.0f, 0.0f, 1.0f});
  }
  return json::array({q[0] / norm, q[1] / norm, q[2] / norm, q[3] / norm});
}

json rigidPoseArgs(const RigidPose &pose) {
  return {{"position", pose.position}, {"quaternion", pose.quaternion}};
}

const char *transformSpace(TransformSpace space) {
  return space == TransformSpace::World ? "world" : "local";
}

void applyNodeOptions(json &args, const SceneNodeOptions &node) {
  if (node.parent) args["parent"] = *node.parent;
  if (node.name) args["name"] = *node.name;
  if (node.tags != json::object()) args["tags"] = node.tags;
  if (node.pose) args["pose"] = rigidPoseArgs(*node.pose);
  if (node.geometryScale) args["geometry_scale"] = *node.geometryScale;
}

// A failed create leaves its uploaded buffers unreferenced on the Host.
struct PendingUploads {
  FrameVizClient &client;
  std::vector<std::string> ids;

  ~PendingUploads() {
    for (const auto &id : ids) {
      try {
        client.sendCommand("free_buffer", {{"buffer_id", id}});
      } catch (const std::exception &) {
      }
    }
  }

  void commit() { ids.clear(); }
};

json bufferArgs(const BufferRef &buffer) {
  return {{"buffer_id", buffer.buffer_id}, {"dtype", buffer.dtype},
          {"shape", buffer.shape}};
}

Vec3 requireVec3(const json &value, const std::string &label) {
  if (!value.is_array() || value.size() != 3) {
    throw std::runtime_error("Invalid " + label + ": expected array of length 3");
  }
  Vec3 out{};
  for (size_t i = 0; i < 3; ++i) {
    if (!value[i].is_number()) {
      throw std::runtime_error("Invalid " + label + ": expected numeric values");
    }
    out[i] = value[i].get<float>();
  }
  return out;
}

Quat requireQuat(const json &value, const std::string &label) {
  if (!value.is_array() || value.size() != 4) {
    throw std::runtime_error("Invalid " + label + ": expected array of length 4");
  }
  Quat out{};
  for (size_t i = 0; i < 4; ++i) {
    if (!value[i].is_number()) {
      throw std::runtime_error("Invalid " + label + ": expected numeric values");
    }
    out[i] = value[i].get<float>();
  }
  return out;
}

std::string instanceTypeToString(InstanceType type) {
  switch (type) {
  case InstanceType::BOX:
    return "box";
  case InstanceType::SPHERE:
    return "sphere";
  case InstanceType::AXES:
    return "axes";
  }
  return "box";
}

std::string facesFormatToString(FacesFormat fmt) {
  switch (fmt) {
  case FacesFormat::TRI:
    return "tri";
  case FacesFormat::POLY:
    return "poly";
  }
  return "tri";
}

json colorToJson(const Color &c) {
  detail::validateColorComponents(c, "color");
  json arr = json::array();
  for (float val : c) {
    arr.push_back(val);
  }
  return arr;
}

} // namespace

// ─────────────────────────────────────────────────────────────────────────────
// Viz: Static factory & lifecycle
// ─────────────────────────────────────────────────────────────────────────────

std::unique_ptr<Viz> Viz::open(const std::string &url, const std::string &title,
                               int width, int height, bool windowDecorations,
                               const std::optional<std::string>& shareScene,
                               int windowMode) {
  std::string resolved_url = resolveWsUrl(url);
  auto client = std::make_unique<FrameVizClient>(resolved_url);
  try {
    client->connect();
  } catch (const std::exception &) {
    // Connection failed — try to auto-start the host and retry.
    ensureHostRunning(resolved_url);
    client = std::make_unique<FrameVizClient>(resolved_url);
    client->connect();
  }

  // Use existing scene or create new one
  std::string scene_id;
  bool owns_scene;

  if (shareScene.has_value()) {
    // Use existing scene
    scene_id = *shareScene;
    owns_scene = false;
  } else {
    // Create new scene
    json scene_result = client->sendCommand("create_scene", json::object());
    scene_id = scene_result.value("scene_id", "");
    if (scene_id.empty()) {
      throw std::runtime_error("Failed to create scene");
    }
    owns_scene = true;
  }

  // Create view
  json view_args = {{"scene_id", scene_id},
                    {"title", title},
                    {"width", width},
                    {"height", height},
                    {"window_decorations", windowDecorations}};
  json view_result = client->sendCommand("create_view", view_args);
  std::string view_id = view_result.value("view_id", "");
  if (view_id.empty()) {
    throw std::runtime_error("Failed to create view");
  }

  auto open_browser = [&]() {
    int ws_port = getWsPortFromUrl(resolved_url);
    std::string viewer_url =
        buildViewerUrl(getViewerUrl(), view_id, ws_port, "balanced");

    if (!std::regex_search(viewer_url, std::regex(R"(^https?://(127\.0\.0\.1|localhost|\[::1\])(:[0-9]+)?(/|$))"))) {
      throw std::runtime_error("Automatic authenticated Viewer opening requires a loopback URL");
    }
    const char* explicit_token = std::getenv("FRAMEVIZ_AUTH_TOKEN");
    auto token = explicit_token ? std::optional<std::string>(explicit_token) : getTokenFromDiscovery();
    if (token) {
      static const char hex[] = "0123456789ABCDEF";
      std::string encoded;
      for (unsigned char c : *token) { encoded += '%'; encoded += hex[c >> 4]; encoded += hex[c & 15]; }
      viewer_url = viewer_url.substr(0, viewer_url.find('#')) + "#token=" + encoded;
    }
#if defined(_WIN32) || defined(_WIN64)
    ShellExecuteA(nullptr, "open", viewer_url.c_str(), nullptr, nullptr, SW_SHOWNORMAL);
#else
#if defined(__APPLE__)
    const char* program = "open";
#else
    const char* program = "xdg-open";
#endif
    char* argv[] = {const_cast<char*>(program), const_cast<char*>(viewer_url.c_str()), nullptr};
    pid_t pid;
    if (posix_spawnp(&pid, program, nullptr, nullptr, argv, environ) != 0) throw std::runtime_error("Unable to open Viewer");
    int status; waitpid(pid, &status, 0);
#endif
  };

  // Match Python SDK behavior:
  //   0: no auto-open
  //   1: browser only
  //   2: try tauri then browser
  bool opened_via_tauri = false;
  int normalized_window_mode = windowMode;
  if (normalized_window_mode < 0 || normalized_window_mode > 2) {
    normalized_window_mode = 2;
  }

  if (normalized_window_mode == 1) {
    open_browser();
  } else if (normalized_window_mode == 2) {
    if (tryOpenTauriWindow(view_id, title, width, height, std::nullopt,
                          std::nullopt, "", scene_id, "balanced",
                          windowDecorations)) {
      opened_via_tauri = true;
    } else {
      open_browser();
    }
  }

  auto viz = std::unique_ptr<Viz>(
      new Viz(std::move(client), scene_id, view_id, opened_via_tauri, true,
              true));
  if (normalized_window_mode != 0 && !viz->waitForViewer(std::chrono::seconds(10))) {
    std::cerr << "[FrameViz] Viewer not ready within timeout. "
              << "Continuing without viewer readiness." << std::endl;
  }
  return viz;
}

std::unique_ptr<Viz> Viz::connect(const std::string &url,
                                  const std::string &view_id,
                                  std::chrono::seconds timeout) {
  std::string resolved_url = resolveWsUrl(url);
  auto client = std::make_unique<FrameVizClient>(resolved_url);
  try {
    client->connect(timeout);
  } catch (const std::exception &) {
    ensureHostRunning(resolved_url);
    client = std::make_unique<FrameVizClient>(resolved_url);
    client->connect(timeout);
  }

  auto start = std::chrono::steady_clock::now();
  constexpr auto poll_interval = std::chrono::milliseconds(500);
  std::vector<std::string> last_view_ids;

  while (std::chrono::steady_clock::now() - start < timeout) {
    json result = client->sendCommand("list_views", json::object());
    std::vector<std::pair<std::string, std::string>> views;
    last_view_ids.clear();
    if (result.contains("views") && result["views"].is_array()) {
      for (const auto &item : result["views"]) {
        if (!item.is_object()) {
          continue;
        }
        std::string view_id = item.value("view_id", "");
        std::string scene_id = item.value("scene_id", "");
        if (!view_id.empty() && !scene_id.empty()) {
          views.emplace_back(view_id, scene_id);
          last_view_ids.push_back(view_id);
        }
      }
    }

    std::string selected_view_id;
    std::string selected_scene_id;

    if (!view_id.empty()) {
      for (const auto &entry : views) {
        if (entry.first == view_id) {
          selected_view_id = entry.first;
          selected_scene_id = entry.second;
          break;
        }
      }
    } else {
      if (views.size() == 1) {
        selected_view_id = views[0].first;
        selected_scene_id = views[0].second;
      } else if (views.size() > 1) {
        std::ostringstream oss;
        for (size_t i = 0; i < last_view_ids.size(); ++i) {
          if (i > 0) {
            oss << ", ";
          }
          oss << last_view_ids[i];
        }
        throw std::runtime_error(
            "Multiple views are available: " + oss.str() +
            ". Specify Viz::connect(url, view_id, timeout) explicitly.");
      }
    }

    if (!selected_view_id.empty() && !selected_scene_id.empty()) {
      auto viz = std::unique_ptr<Viz>(
          new Viz(std::move(client), selected_scene_id, selected_view_id, false,
                  false, false));
      return viz;
    }
    std::this_thread::sleep_for(poll_interval);
  }

  if (!view_id.empty()) {
    std::ostringstream oss;
    if (!last_view_ids.empty()) {
      oss << " Available view_ids: ";
      for (size_t i = 0; i < last_view_ids.size(); ++i) {
        if (i > 0) {
          oss << ", ";
        }
        oss << last_view_ids[i];
      }
      oss << ".";
    }
    throw std::runtime_error("View '" + view_id + "' not found within " +
                             std::to_string(timeout.count()) + "s." +
                             oss.str());
  }

  throw std::runtime_error(
      "No available view found within " + std::to_string(timeout.count()) +
      "s. Open a view first or specify Viz::connect(url, view_id, timeout).");
}

Viz::Viz(std::unique_ptr<FrameVizClient> client, const std::string &scene_id,
         const std::string &view_id, bool opened_via_tauri, bool owns_view,
         bool owns_scene)
    : m_client(std::move(client)), m_sceneId(scene_id), m_viewId(view_id),
      m_bufferCounter(0), m_openedViaTauri(opened_via_tauri),
      m_ownsView(owns_view),
      m_ownsScene(owns_scene) {}

Viz::~Viz() = default;

Viz::Viz(Viz &&) noexcept = default;
Viz &Viz::operator=(Viz &&) noexcept = default;

std::string Viz::sceneId() const { return m_sceneId; }
std::string Viz::viewId() const { return m_viewId; }
bool Viz::waitForViewer(std::chrono::seconds timeout) {
  auto event = m_client->waitForEvent(
      "viewer_ready",
      [this](const json &data) {
        return data.value("view_id", "") == m_viewId;
      },
      timeout);
  return event.has_value();
}
void Viz::close() {
  if (!m_client) {
    return;
  }
  if (m_ownsView) {
    bool destroySent = false;
    try {
      m_client->sendCommand("destroy_view", {{"view_id", m_viewId}});
      destroySent = true;
    } catch (...) {
      // Best-effort teardown; ignore errors.
    }
    // Wait for viewer-side cleanup to complete before proceeding (#44).
    // Only wait if the destroy command was actually sent; otherwise the
    // event will never arrive and we'd stall for the full timeout.
    if (destroySent) {
      try {
        m_client->waitForEvent(
            "view_destroyed",
            [this](const json &data) {
              return data.value("view_id", "") == m_viewId;
            },
            std::chrono::seconds(2));
      } catch (...) {
      }
    }
    if (m_openedViaTauri) {
      tryCloseTauriWindow(m_viewId);
    }

    // Check if this is the last view using this scene.
    bool has_other_views = false;
    if (!m_sceneId.empty()) {
      try {
        json result = m_client->sendCommand("list_views", json::object());
        if (result.contains("views") && result["views"].is_array()) {
          for (const auto &view : result["views"]) {
            if (view.contains("scene_id") && view["scene_id"] == m_sceneId) {
              has_other_views = true;
              break;
            }
          }
        }
      } catch (...) {
        has_other_views = true;
      }
    }

    // Only destroy scene if we're the last view using it
    if (!has_other_views && !m_sceneId.empty()) {
      try {
        m_client->sendCommand("destroy_scene", {{"scene_id", m_sceneId}});
      } catch (...) {
      }
      m_ownsScene = false;
    }
  }
  m_client->close();
}

// ─────────────────────────────────────────────────────────────────────────────
// Primitives: Private helper
// ─────────────────────────────────────────────────────────────────────────────

Handle Viz::addPrimitive(const std::string &ptype, const json &params, Vec3 pos,
                         Quat quat, Color color, const SceneNodeOptions &node) {
  json args = {{"scene_id", m_sceneId},
               {"type", ptype},
               {"pose", {{"pos", toList(pos)}, {"quat", normalizeQuat(quat)}}},
               {"color", colorToJson(color)},
               {"params", params}};
  applyNodeOptions(args, node);
  json result = m_client->sendCommand("add_primitive", args);
  return result.value("handle", "");
}

// ─────────────────────────────────────────────────────────────────────────────
// Primitives: Public API
// ─────────────────────────────────────────────────────────────────────────────

Handle Viz::addBox(Vec3 size, Vec3 pos, Quat quat, Color color, const SceneNodeOptions &node) {
  json params = {{"size", toList(size)}};
  return addPrimitive("box", params, pos, quat, color, node);
}

Handle Viz::addSphere(float radius, Vec3 pos, Quat quat, Color color, const SceneNodeOptions &node) {
  json params = {{"radius", radius}};
  return addPrimitive("sphere", params, pos, quat, color, node);
}

Handle Viz::addCylinder(float radius, float height, Vec3 pos, Quat quat,
                        Color color, const SceneNodeOptions &node) {
  json params = {{"radius", radius}, {"height", height}};
  return addPrimitive("cylinder", params, pos, quat, color, node);
}

Handle Viz::addCone(float radius, float height, Vec3 pos, Quat quat,
                    Color color, const SceneNodeOptions &node) {
  json params = {{"radius", radius}, {"height", height}};
  return addPrimitive("cone", params, pos, quat, color, node);
}

Handle Viz::addAxes(float length, float radius, Vec3 pos, Quat quat, const SceneNodeOptions &node) {
  json params = {{"length", length}, {"radius", radius}};
  return addPrimitive("axes", params, pos, quat, {1.0f, 1.0f, 1.0f}, node);
}

Handle Viz::addArrow(Vec3 start, Vec3 end, float radius, Color color, const SceneNodeOptions &node) {
  json params = {
      {"radius", radius}, {"start", toList(start)}, {"end", toList(end)}};
  return addPrimitive("arrow", params, {0.0f, 0.0f, 0.0f},
                      {0.0f, 0.0f, 0.0f, 1.0f}, color, node);
}

Handle Viz::addPlane(float width, float height, Vec3 pos, Quat quat,
                     Color color, const SceneNodeOptions &node) {
  json params = {{"width", width}, {"height", height}};
  return addPrimitive("plane", params, pos, quat, color, node);
}

// ─────────────────────────────────────────────────────────────────────────────
// Points / Lines / Mesh
// ─────────────────────────────────────────────────────────────────────────────

Handle Viz::addPoints(const std::vector<float> &positions, Color color,
                      float size, const SceneNodeOptions &node) {
  return addPointCloud(positions, {}, size, color, node);
}

Handle Viz::addPoints(const std::vector<float> &positions,
                      const std::vector<Color> &colors, float size,
                      const SceneNodeOptions &node) {
  return addPointCloud(positions, colors, size, std::nullopt, node);
}

Handle Viz::addPointCloud(const std::vector<float> &positions,
                          const std::vector<Color> &colors, float size,
                          std::optional<Color> uniformColor, const SceneNodeOptions &node) {
  if (positions.size() % 3 != 0) {
    throw std::invalid_argument("addPoints.positions must contain three values per point");
  }
  const size_t count = positions.size() / 3;
  const auto packed = colors.empty() ? std::vector<uint8_t>{}
                                     : packColorsToU8(colors, "addPoints.colors", count);
  json args = {{"scene_id", m_sceneId}, {"size", size}};
  applyNodeOptions(args, node);
  if (uniformColor) args["color"] = colorToJson(*uniformColor);

  PendingUploads uploads{*m_client, {}};
  auto upload = [&](const void *data, size_t bytes, const char *dtype, int length) {
    return bufferArgs(uploadBuffer(data, bytes, dtype, {length, 3}, &uploads.ids));
  };
  json chunks = json::array();
  for (size_t start = 0; start < count || start == 0; start += kPointsChunkSize) {
    const auto length = std::min(kPointsChunkSize, count - start);
    const auto *position = start == 0 ? positions.data() : positions.data() + start * 3;
    json chunk = {{"positions", upload(position, length * 3 * sizeof(float),
                                       "f32", static_cast<int>(length))}};
    if (!packed.empty()) {
      chunk["colors"] = upload(packed.data() + start * 3, length * 3,
                               "u8", static_cast<int>(length));
    }
    chunks.push_back(std::move(chunk));
  }
  if (chunks.size() == 1) args.update(chunks.front());
  else args["chunks"] = std::move(chunks);
  auto result = m_client->sendCommand("add_points", args);
  uploads.commit();
  return result.at("handle").get<Handle>();
}

Handle Viz::addLines(const std::vector<float> &positions,
                     const std::vector<uint32_t> &indices, float width,
                     Color color, const SceneNodeOptions &node) {
  PendingUploads uploads{*m_client, {}};
  int n_verts = static_cast<int>(positions.size() / 3);
  BufferRef pos_buf = uploadBuffer(
      positions.data(), positions.size() * sizeof(float), "f32", {n_verts, 3}, &uploads.ids);

  json args = {{"scene_id", m_sceneId},
               {"positions",
                {{"buffer_id", pos_buf.buffer_id},
                 {"dtype", pos_buf.dtype},
                 {"shape", pos_buf.shape}}},
               {"width", width},
               {"color", colorToJson(color)}};

  if (!indices.empty()) {
    int n_edges = static_cast<int>(indices.size() / 2);
    BufferRef idx_buf = uploadBuffer(
        indices.data(), indices.size() * sizeof(uint32_t), "u32", {n_edges, 2}, &uploads.ids);
    args["indices"] = {{"buffer_id", idx_buf.buffer_id},
                       {"dtype", idx_buf.dtype},
                       {"shape", idx_buf.shape}};
  }

  applyNodeOptions(args, node);
  json result = m_client->sendCommand("add_lines", args);
  uploads.commit();
  return result.value("handle", "");
}

Handle Viz::addMesh(const std::vector<float> &vertices,
                    const std::vector<uint32_t> &faces, FacesFormat format,
                    Color color, const std::vector<Color> &face_colors,
                    std::optional<float> alpha, bool wireframe,
                    bool smooth_shading, const SceneNodeOptions &node) {
  PendingUploads uploads{*m_client, {}};
  validateColorComponents(color, "addMesh.color");
  const bool has_face_colors = !face_colors.empty();
  const bool is_default_color =
      color.size() == 3 && color[0] == 1.0f && color[1] == 1.0f && color[2] == 1.0f;
  if (has_face_colors && !is_default_color) {
    throw std::runtime_error("color and face_colors are mutually exclusive");
  }

  int v_count = static_cast<int>(vertices.size() / 3);
  BufferRef vert_buf = uploadBuffer(
      vertices.data(), vertices.size() * sizeof(float), "f32", {v_count, 3}, &uploads.ids);

  json args = {{"scene_id", m_sceneId},
               {"vertices",
                {{"buffer_id", vert_buf.buffer_id},
                 {"dtype", vert_buf.dtype},
                 {"shape", vert_buf.shape}}}};

  size_t face_count = 0;
  std::vector<uint32_t> poly_counts;
  std::vector<uint32_t> poly_indices;

  // Faces (handle TRI and POLY formats)
  if (format == FacesFormat::POLY) {
    // POLY format: faces = {m,k1..km,n,p1..pn,...}
    if (faces.empty()) {
      throw std::runtime_error("POLY format requires faces data");
    }
    args["faces_format"] = "poly";

    poly_counts.reserve(faces.size() / 4);
    poly_indices.reserve(faces.size());
    size_t i = 0;
    while (i < faces.size()) {
      uint32_t count = faces[i++];
      if (count == 0) {
        throw std::runtime_error("POLY face count must be > 0");
      }
      if (i + count > faces.size()) {
        throw std::runtime_error("POLY faces data is incomplete");
      }
      poly_counts.push_back(count);
      for (uint32_t j = 0; j < count; ++j) {
        poly_indices.push_back(faces[i++]);
      }
    }
    face_count = poly_counts.size();

    int count_size = static_cast<int>(poly_counts.size());
    BufferRef count_buf =
        uploadBuffer(poly_counts.data(), poly_counts.size() * sizeof(uint32_t),
                     "u32", {count_size}, &uploads.ids);

    int indices_size = static_cast<int>(poly_indices.size());
    BufferRef indices_buf =
        uploadBuffer(poly_indices.data(), poly_indices.size() * sizeof(uint32_t),
                     "u32", {indices_size}, &uploads.ids);

    args["faces"] = {
        {"counts", {{"buffer_id", count_buf.buffer_id},
                     {"dtype", count_buf.dtype},
                     {"shape", count_buf.shape}}},
        {"indices", {{"buffer_id", indices_buf.buffer_id},
                      {"dtype", indices_buf.dtype},
                      {"shape", indices_buf.shape}}}
    };
  } else {
    // TRI format: [F, 3] triangular indices (default)
    args["faces_format"] = "tri";
    if (faces.size() % 3 != 0) {
      throw std::runtime_error("TRI format requires faces.size() % 3 == 0");
    }
    int f_count = static_cast<int>(faces.size() / 3);
    face_count = static_cast<size_t>(f_count);
    BufferRef face_buf = uploadBuffer(
        faces.data(), faces.size() * sizeof(uint32_t), "u32", {f_count, 3}, &uploads.ids);
    args["faces"] = {{"buffer_id", face_buf.buffer_id},
                     {"dtype", face_buf.dtype},
                     {"shape", face_buf.shape}};
  }

  if (has_face_colors) {
    if (face_count == 0) {
      throw std::runtime_error("face_colors requires non-empty faces");
    }
    if (face_colors.size() != face_count) {
      throw std::runtime_error("face_colors size must match face count");
    }
    auto packed = packColorsToU8(face_colors, "face_colors", face_count);
    BufferRef col_buf = uploadBuffer(
        packed.data(), packed.size() * sizeof(uint8_t), "u8",
        {static_cast<int>(face_count), 3}, &uploads.ids);
    args["colors"] = {{"buffer_id", col_buf.buffer_id},
                      {"dtype", col_buf.dtype},
                      {"shape", col_buf.shape}};
  }

  if (!has_face_colors) {
    args["color"] = colorToJson(color);
  }

  // Add alpha parameter if provided
  if (alpha.has_value()) {
    float alpha_value = alpha.value();
    if (alpha_value < 0.0f || alpha_value > 1.0f) {
      throw std::runtime_error("alpha must be in [0.0, 1.0]");
    }
    args["alpha"] = alpha_value;
  }

  // Add wireframe parameter (only send if true to reduce bandwidth)
  if (wireframe) {
    args["wireframe"] = wireframe;
  }

  // Optimization: only send when disabling, relying on core default=true.
  // Keep behavior aligned with Python SDK (frameviz/viz.py).
  if (!smooth_shading) {
    args["smooth_shading"] = smooth_shading;
  }

  applyNodeOptions(args, node);
  json result = m_client->sendCommand("add_mesh", args);
  uploads.commit();
  return result.value("handle", "");
}

Handle Viz::loadMesh(const std::string &url, Vec3 pos, Quat quat, Vec3 scale,
                     std::optional<Color> color, const SceneNodeOptions &node) {
  json args = {{"scene_id", m_sceneId},
               {"url", url},
               {"pose", {{"pos", toList(pos)}, {"quat", normalizeQuat(quat)}}},
               {"scale", toList(scale)}};
  if (color.has_value()) {
    args["color"] = colorToJson(color.value());
  }
  if (node.geometryScale) args.erase("scale");
  applyNodeOptions(args, node);
  json result = m_client->sendCommand("load_mesh", args);
  return result.value("handle", "");
}

// ─────────────────────────────────────────────────────────────────────────────
// Instancing
// ─────────────────────────────────────────────────────────────────────────────

Handle Viz::addInstances(InstanceType type, const std::vector<float> &positions,
                         const std::vector<float> &quats,
                         const std::vector<float> &scales,
                         const std::vector<Color> &colors,
                         std::optional<Color> uniform_color,
                         std::optional<float> alpha,
                         const std::optional<Vec3> &size, const SceneNodeOptions &node) {
  PendingUploads uploads{*m_client, {}};
  int n = static_cast<int>(positions.size() / 3);
  BufferRef pos_buf = uploadBuffer(
      positions.data(), positions.size() * sizeof(float), "f32", {n, 3}, &uploads.ids);

  json args = {{"scene_id", m_sceneId},
               {"type", instanceTypeToString(type)},
               {"positions",
                {{"buffer_id", pos_buf.buffer_id},
                 {"dtype", pos_buf.dtype},
                 {"shape", pos_buf.shape}}}};

  // Build primitive params based on type and size
  json params = json::object();
  if (size.has_value()) {
    Vec3 s = size.value();
    switch (type) {
    case InstanceType::BOX:
      // Box: size = [width, height, depth]
      params["size"] = {s[0], s[1], s[2]};
      break;
    case InstanceType::SPHERE:
      // Sphere: size.x = radius
      params["radius"] = s[0];
      break;
    case InstanceType::AXES:
      // Axes: size.x = length, size.y = radius
      params["length"] = s[0];
      params["radius"] = s[1];
      break;
    }
  }
  args["params"] = params;

  if (!quats.empty()) {
    BufferRef q_buf =
        uploadBuffer(quats.data(), quats.size() * sizeof(float), "f32", {n, 4}, &uploads.ids);
    args["quats"] = {{"buffer_id", q_buf.buffer_id},
                     {"dtype", q_buf.dtype},
                     {"shape", q_buf.shape}};
  }

  if (!scales.empty()) {
    BufferRef s_buf = uploadBuffer(scales.data(), scales.size() * sizeof(float),
                                   "f32", {n, 3}, &uploads.ids);
    args["scales"] = {{"buffer_id", s_buf.buffer_id},
                      {"dtype", s_buf.dtype},
                      {"shape", s_buf.shape}};
  }

  if (!colors.empty()) {
    if (static_cast<int>(colors.size()) != n) {
      throw std::runtime_error("addInstances.colors size must match instance count");
    }
    auto packed = packColorsToU8(colors, "addInstances.colors", static_cast<size_t>(n));
    BufferRef c_buf = uploadBuffer(
        packed.data(), packed.size() * sizeof(uint8_t), "u8", {n, 3}, &uploads.ids);
    args["colors"] = {{"buffer_id", c_buf.buffer_id},
                      {"dtype", c_buf.dtype},
                      {"shape", c_buf.shape}};
  }

  if (uniform_color.has_value()) {
    const auto &c = uniform_color.value();
    validateColorComponents(c, "addInstances.color");
    args["color"] = json::array({c[0], c[1], c[2]});
  }
  if (alpha.has_value()) {
    args["alpha"] = alpha.value();
  }

  applyNodeOptions(args, node);
  json result = m_client->sendCommand("add_instances", args);
  uploads.commit();
  return result.value("handle", "");
}

void Viz::updateInstances(Handle handle, const std::vector<float> &positions,
                          const std::vector<float> &quats,
                          const std::vector<float> &scales,
                          const std::vector<Color> &colors,
                          std::optional<Color> uniform_color,
                          std::optional<float> alpha) {
  json args = {{"handle", handle}};

  // Calculate instance count from any non-empty array
  int n = 0;
  if (!positions.empty()) {
    n = static_cast<int>(positions.size() / 3);
  } else if (!quats.empty()) {
    n = static_cast<int>(quats.size() / 4);
  } else if (!scales.empty()) {
    n = static_cast<int>(scales.size() / 3);
  } else if (!colors.empty()) {
    n = static_cast<int>(colors.size());
  }

  // Upload buffers independently (support partial updates)
  if (!positions.empty()) {
    BufferRef pos_buf = uploadBuffer(
        positions.data(), positions.size() * sizeof(float), "f32", {n, 3});
    args["positions"] = {{"buffer_id", pos_buf.buffer_id},
                         {"dtype", pos_buf.dtype},
                         {"shape", pos_buf.shape}};
  }

  if (!quats.empty()) {
    BufferRef q_buf = uploadBuffer(quats.data(), quats.size() * sizeof(float),
                                   "f32", {n, 4});
    args["quats"] = {{"buffer_id", q_buf.buffer_id},
                     {"dtype", q_buf.dtype},
                     {"shape", q_buf.shape}};
  }

  if (!scales.empty()) {
    BufferRef s_buf = uploadBuffer(
        scales.data(), scales.size() * sizeof(float), "f32", {n, 3});
    args["scales"] = {{"buffer_id", s_buf.buffer_id},
                      {"dtype", s_buf.dtype},
                      {"shape", s_buf.shape}};
  }

  if (!colors.empty()) {
    if (n <= 0) {
      throw std::runtime_error("updateInstances.colors requires a valid instance count");
    }
    if (static_cast<int>(colors.size()) != n) {
      throw std::runtime_error("updateInstances.colors size must match instance count");
    }
    auto packed = packColorsToU8(colors, "updateInstances.colors", static_cast<size_t>(n));
    BufferRef c_buf = uploadBuffer(
        packed.data(), packed.size() * sizeof(uint8_t), "u8", {n, 3});
    args["colors"] = {{"buffer_id", c_buf.buffer_id},
                      {"dtype", c_buf.dtype},
                      {"shape", c_buf.shape}};
  }

  if (uniform_color.has_value()) {
    const auto &c = uniform_color.value();
    validateColorComponents(c, "updateInstances.color");
    args["color"] = json::array({c[0], c[1], c[2]});
  }
  if (alpha.has_value()) {
    args["alpha"] = alpha.value();
  }

  // Only send command if there's something to update
  if (n > 0 || uniform_color.has_value() || alpha.has_value()) {
    m_client->sendCommand("update_instances", args);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Transforms
// ─────────────────────────────────────────────────────────────────────────────

Handle Viz::addNode(const SceneNodeOptions &node) {
  json args = {{"scene_id", m_sceneId}};
  applyNodeOptions(args, node);
  return m_client->sendCommand("add_node", args).at("handle").get<Handle>();
}

void Viz::setParent(Handle handle, const std::optional<Handle> &parent,
                    const std::optional<RigidPose> &localTransform) {
  json args = {{"scene_id", m_sceneId}, {"handle", handle},
               {"parent", parent ? json(*parent) : json(nullptr)}};
  if (localTransform) args["local_transform"] = rigidPoseArgs(*localTransform);
  m_client->sendCommand("set_parent", args);
}

void Viz::setObjectMetadata(Handle handle, const std::optional<std::string> &name,
                            const json &tags) {
  json args = {{"scene_id", m_sceneId}, {"handle", handle}, {"tags", tags}};
  if (name) args["name"] = *name;
  m_client->sendCommand("set_object_metadata", args);
}

void Viz::setGeometryScale(Handle handle, Vec3 scale) {
  m_client->sendCommand("set_geometry_scale", {{"scene_id", m_sceneId},
                        {"handle", handle}, {"geometry_scale", scale}});
}

void Viz::setTransform(Handle handle, const RigidPose &pose) {
  m_client->sendCommand("set_transform", {{"scene_id", m_sceneId},
                        {"handle", handle}, {"pose", rigidPoseArgs(pose)}});
}

void Viz::setTransform(Handle handle, Vec3 pos, Quat quat) {
  json pose = {{"pos", toList(pos)}, {"quat", normalizeQuat(quat)}};
  m_client->sendCommand(
      "set_transform",
      {{"handle", handle}, {"pose", pose}, {"scene_id", m_sceneId}});
}

void Viz::setObjectTransforms(const std::vector<TransformItem> &items) {
  json payload = json::array();
  for (const auto &item : items) {
    json pose = {{"pos", toList(item.pose.pos)},
                 {"quat", normalizeQuat(item.pose.quat)}};
    // Add scale if not default
    if (item.pose.scale[0] != 1.0f || item.pose.scale[1] != 1.0f ||
        item.pose.scale[2] != 1.0f) {
      pose["scale"] = toList(item.pose.scale);
    }
    payload.push_back({{"handle", item.handle}, {"pose", pose}});
  }
  if (payload.empty())
    return;
  m_client->sendCommand("set_object_transforms", {{"scene_id", m_sceneId}, {"items", payload}});
}

Pose Viz::getTransform(Handle handle, TransformSpace space) {
  json result = m_client->sendCommand("get_transform", {{"handle", handle},
                        {"scene_id", m_sceneId}, {"space", transformSpace(space)}});
  Pose pose;
  if (result.contains("pose")) {
    auto p = result["pose"];
    if (!p.is_object()) {
      throw std::runtime_error("Invalid get_transform response: pose must be an object");
    }
    if (p.contains("pos")) {
      pose.pos = requireVec3(p["pos"], "pose.pos");
    }
    if (p.contains("quat")) {
      pose.quat = requireQuat(p["quat"], "pose.quat");
    }
    if (p.contains("scale")) {
      pose.scale = requireVec3(p["scale"], "pose.scale");
    }
  }
  return pose;
}

std::array<double, 16> Viz::getTransformMatrix(Handle handle, TransformSpace space) {
  auto result = m_client->sendCommand("get_transform", {{"handle", handle},
      {"scene_id", m_sceneId}, {"space", transformSpace(space)}, {"matrix", true}});
  return result.at("matrix").get<std::array<double, 16>>();
}

std::optional<Color> Viz::getColor(Handle handle) {
  json result = m_client->sendCommand("get_color", {{"handle", handle}});
  if (result.contains("has_vertex_colors") && result["has_vertex_colors"].get<bool>()) {
    return std::nullopt;
  }
  if (!result.contains("rgba") || !result["rgba"].is_array() || result["rgba"].size() != 4) {
    throw std::runtime_error("Invalid get_color response: expected RGBA list of length 4");
  }
  Color rgba;
  rgba.reserve(4);
  for (const auto &value : result["rgba"]) {
    rgba.push_back(value.get<float>());
  }
  return rgba;
}

float Viz::getAlpha(Handle handle) {
  json result = m_client->sendCommand("get_alpha", {{"handle", handle}});
  if (result.contains("alpha")) {
    return result["alpha"].get<float>();
  }
  return 1.0f;
}

// ─────────────────────────────────────────────────────────────────────────────
// Object Management
// ─────────────────────────────────────────────────────────────────────────────

void Viz::removeObject(Handle handle) {
  m_overlayHandles.erase(handle);
  // Try scene-scoped removal first (for 3D objects)
  try {
    m_client->sendCommand("remove_object",
                          {{"handle", handle}, {"scene_id", m_sceneId}});
  } catch (const std::runtime_error &e) {
    // If ERR_NOT_FOUND, try view-scoped removal (for 2D overlays)
    std::string error_msg = e.what();
    if (error_msg.find("ERR_NOT_FOUND") != std::string::npos) {
      try {
        m_client->sendCommand("remove_object",
                              {{"handle", handle}, {"view_id", m_viewId}});
      } catch (const std::runtime_error &e2) {
        std::string overlay_err = e2.what();
        if (overlay_err.find("ERR_NOT_FOUND") != std::string::npos) {
          std::cerr << "[FrameViz] Warning: removeObject handle not found: "
                    << handle << std::endl;
          return;
        }
        throw;
      }
    } else {
      throw;  // Re-throw other errors
    }
  }
}

void Viz::removeObjects(const std::vector<Handle> &handles) {
  if (handles.empty())
    return;
  std::vector<Handle> expanded_scene;
  expanded_scene.reserve(handles.size());
  std::vector<Handle> overlay_handles;
  overlay_handles.reserve(handles.size());
  for (const auto &handle : handles) {
    if (m_overlayHandles.find(handle) != m_overlayHandles.end()) {
      overlay_handles.push_back(handle);
      m_overlayHandles.erase(handle);
    } else {
      expanded_scene.push_back(handle);
    }
  }
  if (!expanded_scene.empty()) {
    m_client->sendCommand("remove_objects",
                          {{"handles", expanded_scene}, {"scene_id", m_sceneId}});
  }
  if (!overlay_handles.empty()) {
    for (const auto &handle : overlay_handles) {
      try {
        m_client->sendCommand("remove_object",
                              {{"handle", handle}, {"view_id", m_viewId}});
      } catch (const std::runtime_error &) {
      }
    }
  }
}

void Viz::clear() {
  m_client->sendCommand("clear_scene",
                        {{"scene_id", m_sceneId}, {"view_id", m_viewId}});
  m_overlayHandles.clear();
}

Handle Viz::cloneObject(Handle handle) {
  json result = m_client->sendCommand("clone_object", {{"handle", handle}});
  return result.value("handle", "");
}

bool Viz::isObjectAlive(Handle handle) {
  json result = m_client->sendCommand("is_object_alive", {{"handle", handle}});
  return result.value("alive", false);
}

void Viz::setColor(Handle handle, Color rgba) {
  json color_arr = colorToJson(rgba);
  // Ensure RGBA format
  if (color_arr.size() == 3) {
    color_arr.push_back(1.0f);
  }
  m_client->sendCommand(
      "set_color",
      {{"handle", handle}, {"rgba", color_arr}, {"scene_id", m_sceneId}});
}

void Viz::setAlpha(Handle handle, float alpha) {
  if (alpha < 0.0f || alpha > 1.0f) {
    throw std::runtime_error("alpha must be in [0.0, 1.0]");
  }

  m_client->sendCommand(
      "set_alpha",
      {{"handle", handle}, {"alpha", alpha}, {"scene_id", m_sceneId}});
}

void Viz::setVisible(Handle handle, bool visible) {
  m_client->sendCommand(
      "set_visible",
      {{"handle", handle}, {"visible", visible}, {"scene_id", m_sceneId}});
}

// ─────────────────────────────────────────────────────────────────────────────
// Camera
// ─────────────────────────────────────────────────────────────────────────────

void Viz::setCameraPose(Vec3 eye, Vec3 target, Vec3 up) {
  m_client->sendCommand("set_camera_pose", {{"view_id", m_viewId},
                                            {"eye", toList(eye)},
                                            {"target", toList(target)},
                                            {"up", toList(up)}});
}

CameraPose Viz::getCameraPose() {
  json host_result =
      m_client->sendCommand("get_camera_pose", {{"view_id", m_viewId}});
  // Use Viz::waitForEvent so mapped event semantics stay centralized.
  auto event = waitForEvent(
      "camera_pose_response",
      [this, request_id = host_result.value("request_id", "")](const json &data) {
        return data.value("view_id", "") == m_viewId && data.value("request_id", "") == request_id;
      },
      std::chrono::seconds(2));

  if (!event.has_value()) throw std::runtime_error("Viewer did not answer the correlated query");
  json data = host_result;
  const bool has_event = event.has_value() && event->is_object();
  if (has_event) {
    data = event.value();
  } else if (!m_warnedCameraPoseFallback) {
    std::cerr << "[FrameViz] Warning: getCameraPose viewer event missing; using fallback."
              << std::endl;
    m_warnedCameraPoseFallback = true;
  }

  CameraPose pose;
  if (data.contains("eye")) {
    pose.eye = requireVec3(data["eye"], "eye");
  }
  if (data.contains("target")) {
    pose.target = requireVec3(data["target"], "target");
  }
  if (data.contains("up")) {
    pose.up = requireVec3(data["up"], "up");
  }
  return pose;
}

void Viz::resetCamera(const std::string &mode, const std::string &fit_handle) {
  json args = {{"view_id", m_viewId}, {"mode", mode}};
  if (!fit_handle.empty()) {
    args["fit_handle"] = fit_handle;
  }
  m_client->sendCommand("reset_camera", args);
}

// ─────────────────────────────────────────────────────────────────────────────
// View Configuration
// ─────────────────────────────────────────────────────────────────────────────

void Viz::setViewConfig(const json &config) {
  json args = {{"view_id", m_viewId}, {"config", config}};
  m_client->sendCommand("set_view_config", args);
}

json Viz::getViewConfig() {
  json result = m_client->sendCommand("get_view_config", {{"view_id", m_viewId}});
  if (result.contains("config") && result["config"].is_object()) {
    return result["config"];
  }
  return result;
}

void Viz::setView(const std::string &view_preset, bool fit_all) {
  json args = {{"view_id", m_viewId}, {"view", view_preset}, {"fit_all", fit_all}};
  m_client->sendCommand("set_view", args);
}

void Viz::setRenderMode(const std::string &mode) {
  json args = {{"view_id", m_viewId}, {"mode", mode}};
  m_client->sendCommand("set_render_mode", args);
}

// ─────────────────────────────────────────────────────────────────────────────
// Camera Controls
// ─────────────────────────────────────────────────────────────────────────────

void Viz::setCameraControls(const json &config) {
  json args = {{"view_id", m_viewId}};
  // Merge config parameters directly into args (flat structure)
  for (auto& [key, value] : config.items()) {
    args[key] = value;
  }
  m_client->sendCommand("set_camera_controls", args);
}

json Viz::getCameraControls() {
  json result = m_client->sendCommand("get_camera_controls", {{"view_id", m_viewId}});
  if (result.contains("config") && result["config"].is_object()) {
    return result["config"];
  }
  return result;
}

// ─────────────────────────────────────────────────────────────────────────────
// Picking
// ─────────────────────────────────────────────────────────────────────────────

void Viz::setPickConfig(const json &config) {
  json args = {{"view_id", m_viewId}};
  // Merge config parameters directly into args (flat structure)
  for (auto& [key, value] : config.items()) {
    args[key] = value;
  }
  m_client->sendCommand("set_pick_config", args);
}

json Viz::getPickConfig() {
  static const json kPickConfigDefaults = {
      {"enabled", false},
      {"mode", "object"},
      {"button", 2},
      {"ctrl_modifier", false},
      {"highlight_color", json::array({1, 1, 0})},
      {"marker_size", 0.1},
      {"point_threshold", 0.01},
      {"line_threshold", 0.01},
  };

  json host_result =
      m_client->sendCommand("get_pick_config", {{"view_id", m_viewId}});
  // Use Viz::waitForEvent so mapped event semantics stay centralized.
  auto event = waitForEvent(
      "pick_config_response",
      [this, request_id = host_result.value("request_id", "")](const json &data) {
        return data.value("view_id", "") == m_viewId && data.value("request_id", "") == request_id;
      },
      std::chrono::seconds(2));

  if (!event.has_value()) throw std::runtime_error("Viewer did not answer the correlated query");
  json data = host_result;
  const bool has_event = event.has_value() && event->is_object();
  if (has_event) {
    data = event.value();
  } else if (!m_warnedPickConfigFallback) {
    std::cerr << "[FrameViz] Warning: getPickConfig viewer event missing; using fallback."
              << std::endl;
    m_warnedPickConfigFallback = true;
  }

  json patch = data.is_object() ? data : json::object();
  if (patch.contains("view_id")) {
    patch.erase("view_id");
  }
  json config = kPickConfigDefaults;
  config.merge_patch(patch);
  return config;
}

// ─────────────────────────────────────────────────────────────────────────────
// Gizmo
// ─────────────────────────────────────────────────────────────────────────────

void Viz::attachGizmo(Handle handle, std::optional<int> mask, float size,
                      std::optional<std::string> scale_mode) {
  json args = {
      {"view_id", m_viewId},
      {"handle", handle},
      {"size", size},
  };
  if (mask.has_value()) {
    args["mask"] = mask.value();
  }
  if (scale_mode.has_value()) {
    args["scale_mode"] = scale_mode.value();
  }
  m_client->sendCommand("attach_gizmo", args);
}

void Viz::setGizmoMode(std::optional<int> mask, std::optional<float> size,
                       std::optional<std::string> scale_mode) {
  json args = {{"view_id", m_viewId}};
  if (mask.has_value()) {
    args["mask"] = mask.value();
  }
  if (size.has_value()) {
    args["size"] = size.value();
  }
  if (scale_mode.has_value()) {
    args["scale_mode"] = scale_mode.value();
  }
  m_client->sendCommand("set_gizmo_mode", args);
}

void Viz::detachGizmo() {
  m_client->sendCommand("detach_gizmo", {{"view_id", m_viewId}});
}

// ─────────────────────────────────────────────────────────────────────────────
// Events
// ─────────────────────────────────────────────────────────────────────────────

void Viz::onEvent(const std::string &name, EventHandler handler) {
  m_client->onEvent(name, std::move(handler));
}

void Viz::pollEvents() { m_client->pollEvents(); }

std::optional<json> Viz::waitForEvent(const std::string &event_name,
                                    std::chrono::seconds timeout) {
  return m_client->waitForEvent(event_name, timeout);
}

std::optional<json> Viz::waitForEvent(const std::string &event_name,
                                    std::function<bool(const json &)> filter,
                                    std::chrono::seconds timeout) {
  return m_client->waitForEvent(event_name, std::move(filter), timeout);
}

// ─────────────────────────────────────────────────────────────────────────────
// Text
// ─────────────────────────────────────────────────────────────────────────────

Handle Viz::addText3D(const std::string &text, Vec3 pos, int font_size,
                       Color color,
                       const std::optional<std::string> &background_color, const SceneNodeOptions &node) {
  json args = {{"scene_id", m_sceneId},
               {"text", text},
               {"pos", toList(pos)},
               {"font_size", font_size},
               {"color", colorToJson(color)}};

  if (background_color.has_value()) {
    args["background_color"] = *background_color;
  }

  if (node.pose) args.erase("pos");
  applyNodeOptions(args, node);
  json result = m_client->sendCommand("add_text_3d", args);
  return result.value("handle", "");
}

Handle Viz::addText2D(const std::string &text, int x, int y, int font_size,
                       Color color) {
  json args = {{"view_id", m_viewId},
               {"text", text},
               {"x", x},
               {"y", y},
               {"font_size", font_size},
               {"color", colorToJson(color)}};

  json result = m_client->sendCommand("add_text_2d", args);
  Handle handle = result.value("handle", "");
  if (!handle.empty()) {
    m_overlayHandles.insert(handle);
  }
  return handle;
}

} // namespace frameviz
