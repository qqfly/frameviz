#include <frameviz/business_auth.hpp>
#include <frameviz/client.hpp>
#include <frameviz/host.hpp>

#include <ixwebsocket/IXWebSocketServer.h>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <csignal>
#include <iostream>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <thread>

using json = nlohmann::json;

namespace {

std::atomic<bool> g_running{true};

void signal_handler(int /*signal*/) {
  g_running.store(false);
}

struct ViewerInfo {
  std::string viewer_name;
  std::string view_id;
  std::string scene_id;
};

std::optional<ViewerInfo> try_get_viewer_info(frameviz::FrameVizClient& client, const std::string& viewer_name) {
  try {
    const json result = client.sendCommand("get_viewer_by_name", {{"viewer_name", viewer_name}});
    if (!result.contains("view_id") || result["view_id"].is_null()) {
      return std::nullopt;
    }

    ViewerInfo info;
    info.viewer_name = result.value("viewer_name", viewer_name);
    info.view_id = result.value("view_id", "");
    info.scene_id = result.value("scene_id", "");

    if (info.view_id.empty() || info.scene_id.empty()) {
      return std::nullopt;
    }
    return info;
  } catch (const std::runtime_error& e) {
    const std::string msg = e.what();
    if (msg.find("ERR_NOT_FOUND") != std::string::npos) {
      return std::nullopt;
    }
    throw;
  }
}

std::optional<std::array<double, 3>> parse_vec3(const json& value) {
  if (!value.is_array() || value.size() != 3) {
    return std::nullopt;
  }
  std::array<double, 3> out{};
  for (size_t i = 0; i < 3; ++i) {
    if (!value[i].is_number()) {
      return std::nullopt;
    }
    out[i] = value[i].get<double>();
  }
  return out;
}

std::optional<std::array<double, 4>> parse_quat(const json& value) {
  if (!value.is_array() || value.size() != 4) {
    return std::nullopt;
  }
  std::array<double, 4> out{};
  for (size_t i = 0; i < 4; ++i) {
    if (!value[i].is_number()) {
      return std::nullopt;
    }
    out[i] = value[i].get<double>();
  }
  return out;
}

std::optional<std::array<double, 4>> parse_rgba(const json& value) {
  if (!value.is_array() || (value.size() != 3 && value.size() != 4)) {
    return std::nullopt;
  }
  std::array<double, 4> out{1.0, 1.0, 1.0, 1.0};
  for (size_t i = 0; i < value.size(); ++i) {
    if (!value[i].is_number()) {
      return std::nullopt;
    }
    out[i] = value[i].get<double>();
  }
  return out;
}

struct AppState {
  std::array<double, 3> pos{0.0, 0.0, 0.5};
  std::array<double, 4> quat{0.0, 0.0, 0.0, 1.0};
  std::array<double, 4> rgba{1.0, 0.42, 0.42, 1.0};

  std::string view_id;
  std::string scene_id;
  std::string box_handle;
  bool scene_ready = false;
};

class ExternalBackend {
public:
  ExternalBackend(int ui_port, std::string viewer_name, std::string frameviz_url, bool host_headless)
      : ui_port_(ui_port), viewer_name_(std::move(viewer_name)), frameviz_url_(std::move(frameviz_url)),
        host_headless_(host_headless), client_(frameviz_url_) {}

  bool start() {
    try {
      frameviz::ensureHostRunning(frameviz_url_, 10.0, host_headless_);
    } catch (const std::exception& e) {
      std::cerr << "[Backend] Failed to start FrameViz Host: " << e.what() << std::endl;
      return false;
    }

    try {
      client_.connect(std::chrono::seconds(5));
      std::cout << "[Backend] Connected to FrameViz Host: " << frameviz_url_ << std::endl;
    } catch (const std::exception& e) {
      std::cerr << "[Backend] Failed to connect FrameViz Host: " << e.what() << std::endl;
      return false;
    }

    ui_server_ = std::make_unique<ix::WebSocketServer>(ui_port_, "127.0.0.1");
    ui_server_->setOnClientMessageCallback(
        [this](std::shared_ptr<ix::ConnectionState> connection_state,
               ix::WebSocket& webSocket,
               const ix::WebSocketMessagePtr& msg) {
                if (!business_auth_.accept(webSocket, msg)) return;
          if (msg->type == ix::WebSocketMessageType::Open) {
            std::cout << "[Backend] UI client connected from " << connection_state->getRemoteIp() << std::endl;
            broadcast_state();
            return;
          }
          if (msg->type == ix::WebSocketMessageType::Close) {
            std::cout << "[Backend] UI client disconnected" << std::endl;
            return;
          }
          if (msg->type == ix::WebSocketMessageType::Error) {
            std::cerr << "[Backend] UI WebSocket error: " << msg->errorInfo.reason << std::endl;
            return;
          }
          if (msg->type == ix::WebSocketMessageType::Message) {
            handle_ui_message(msg->str);
          }
        });

    auto listen_result = ui_server_->listen();
    if (!listen_result.first) {
      std::cerr << "[Backend] Failed to start UI server on port " << ui_port_ << ": " << listen_result.second
                << std::endl;
      return false;
    }

    ui_server_->start();
    std::cout << "[Backend] UI WebSocket listening on ws://127.0.0.1:" << ui_port_ << std::endl;
    std::cout << "[Backend] Waiting for viewer '" << viewer_name_ << "' ..." << std::endl;
    return true;
  }

  void run() {
    while (g_running.load()) {
      poll_viewer();
      std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }
  }

  void stop() {
    if (ui_server_) {
      ui_server_->stop();
    }
    client_.close();
  }

private:
  void handle_ui_message(const std::string& payload) {
    json message;
    try {
      message = json::parse(payload);
    } catch (const json::exception&) {
      send_error("Invalid JSON payload");
      return;
    }

    const std::string name = message.value("name", "");
    const json args = message.value("args", json::object());

    std::lock_guard<std::mutex> lock(state_mutex_);

    if (name == "bind_viewer") {
      const std::string requested_name = args.value("viewer_name", "");
      if (!requested_name.empty() && requested_name != viewer_name_) {
        viewer_name_ = requested_name;
        state_.scene_ready = false;
      }
      broadcast_state_locked();
      return;
    }

    if (name == "set_box_pose") {
      auto pos = parse_vec3(args.value("pos", json::array()));
      auto quat = parse_quat(args.value("quat", json::array()));
      if (!pos || !quat) {
        send_error("set_box_pose requires pos[3] and quat[4]");
        return;
      }
      state_.pos = *pos;
      state_.quat = *quat;
      apply_pose_locked();
      broadcast_state_locked();
      return;
    }

    if (name == "set_box_color") {
      auto rgba = parse_rgba(args.value("rgba", json::array()));
      if (!rgba) {
        send_error("set_box_color requires rgb[3] or rgba[4]");
        return;
      }
      state_.rgba = *rgba;
      apply_color_locked();
      broadcast_state_locked();
      return;
    }

    if (name == "reset_box") {
      state_.pos = {0.0, 0.0, 0.5};
      state_.quat = {0.0, 0.0, 0.0, 1.0};
      state_.rgba = {1.0, 0.42, 0.42, 1.0};
      apply_pose_locked();
      apply_color_locked();
      broadcast_state_locked();
      return;
    }

    send_error("Unknown command: " + name);
  }

  void poll_viewer() {
    std::optional<ViewerInfo> info;
    try {
      info = try_get_viewer_info(client_, viewer_name_);
    } catch (const std::exception& e) {
      std::cerr << "[Backend] Viewer query error: " << e.what() << std::endl;
      return;
    }

    if (!info) {
      return;
    }

    std::lock_guard<std::mutex> lock(state_mutex_);
    if (state_.scene_ready && info->view_id == state_.view_id && info->scene_id == state_.scene_id) {
      return;
    }

    std::cout << "[Backend] Binding viewer '" << viewer_name_ << "': view_id=" << info->view_id
              << " scene_id=" << info->scene_id << std::endl;

    state_.view_id = info->view_id;
    state_.scene_id = info->scene_id;
    rebuild_scene_locked();
    broadcast_state_locked();
  }

  void rebuild_scene_locked() {
    if (state_.scene_id.empty()) {
      state_.scene_ready = false;
      return;
    }

    try {
      client_.sendCommand("clear_scene", {{"scene_id", state_.scene_id}});

      client_.sendCommand("add_primitive",
                          {
                              {"scene_id", state_.scene_id},
                              {"type", "axes"},
                              {"params", {{"length", 1.0}}},
                              {"pose", {{"pos", {0.0, 0.0, 0.0}}, {"quat", {0.0, 0.0, 0.0, 1.0}}}},
                              {"color", {1.0, 1.0, 1.0}},
                          });

      client_.sendCommand("add_primitive",
                          {
                              {"scene_id", state_.scene_id},
                              {"type", "plane"},
                              {"params", {{"width", 6.0}, {"height", 6.0}}},
                              {"pose", {{"pos", {0.0, 0.0, 0.0}}, {"quat", {0.0, 0.0, 0.0, 1.0}}}},
                              {"color", {0.3, 0.3, 0.3, 0.5}},
                          });

      const auto box = client_.sendCommand("add_primitive",
                                           {
                                               {"scene_id", state_.scene_id},
                                               {"type", "box"},
                                               {"params", {{"size", {1.0, 1.0, 1.0}}}},
                                               {"pose", {{"pos", state_.pos}, {"quat", state_.quat}}},
                                               {"color", {state_.rgba[0], state_.rgba[1], state_.rgba[2], state_.rgba[3]}},
                                           });

      state_.box_handle = box.value("handle", "");
      state_.scene_ready = !state_.box_handle.empty();
      if (state_.scene_ready) {
        std::cout << "[Backend] Scene initialized, box handle=" << state_.box_handle << std::endl;
      }
    } catch (const std::exception& e) {
      state_.scene_ready = false;
      state_.box_handle.clear();
      std::cerr << "[Backend] Failed to initialize scene: " << e.what() << std::endl;
    }
  }

  void apply_pose_locked() {
    if (!state_.scene_ready || state_.scene_id.empty() || state_.box_handle.empty()) {
      return;
    }

    try {
      client_.sendCommand("set_transform",
                          {
                              {"scene_id", state_.scene_id},
                              {"handle", state_.box_handle},
                              {"pose", {{"pos", state_.pos}, {"quat", state_.quat}}},
                          });
    } catch (const std::exception& e) {
      std::cerr << "[Backend] set_transform failed: " << e.what() << std::endl;
    }
  }

  void apply_color_locked() {
    if (!state_.scene_ready || state_.scene_id.empty() || state_.box_handle.empty()) {
      return;
    }

    try {
      client_.sendCommand("set_color",
                          {
                              {"scene_id", state_.scene_id},
                              {"handle", state_.box_handle},
                              {"rgba", {state_.rgba[0], state_.rgba[1], state_.rgba[2], state_.rgba[3]}},
                          });
    } catch (const std::exception& e) {
      std::cerr << "[Backend] set_color failed: " << e.what() << std::endl;
    }
  }

  void send_error(const std::string& message) {
    json payload = {{"type", "error"}, {"message", message}};
    if (!ui_server_) {
      return;
    }

    for (auto& client : ui_server_->getClients()) {
      if (business_auth_.authorized(client.get())) client->send(payload.dump());
    }
  }

  void broadcast_state() {
    std::lock_guard<std::mutex> lock(state_mutex_);
    broadcast_state_locked();
  }

  void broadcast_state_locked() {
    if (!ui_server_) {
      return;
    }

    json payload = {
        {"type", "state_update"},
        {"viewer_name", viewer_name_},
        {"view_id", state_.view_id},
        {"scene_id", state_.scene_id},
        {"viewer_ready", state_.scene_ready},
        {"box_handle", state_.box_handle},
        {"pose", {{"pos", state_.pos}, {"quat", state_.quat}}},
        {"rgba", {state_.rgba[0], state_.rgba[1], state_.rgba[2], state_.rgba[3]}},
    };

    const std::string encoded = payload.dump();
    for (auto& client : ui_server_->getClients()) {
      if (business_auth_.authorized(client.get())) client->send(encoded);
    }
  }

private:
  int ui_port_;
  std::string viewer_name_;
  std::string frameviz_url_;
  bool host_headless_;

  frameviz::FrameVizClient client_;
  frameviz::BusinessAuth business_auth_;
    std::unique_ptr<ix::WebSocketServer> ui_server_;

  std::mutex state_mutex_;
  AppState state_;
};

}  // namespace

int main(int argc, char* argv[]) {
  int ui_port = 9621;
  std::string viewer_name = "main_viewer";
  std::string frameviz_url = "ws://127.0.0.1:9527";
  bool host_headless = true;

  const char* env_headless = std::getenv("FRAMEVIZ_HOST_HEADLESS");
  if (env_headless) {
    host_headless = std::string(env_headless) == "1";
  }

  for (int i = 1; i < argc; ++i) {
    std::string arg = argv[i];
    if (arg == "--ui-port" && i + 1 < argc) {
      ui_port = std::stoi(argv[++i]);
    } else if (arg == "--viewer-name" && i + 1 < argc) {
      viewer_name = argv[++i];
    } else if (arg == "--frameviz-url" && i + 1 < argc) {
      frameviz_url = argv[++i];
    } else if (arg == "--host-headless" && i + 1 < argc) {
      host_headless = std::string(argv[++i]) == "1";
    } else if (arg == "--help" || arg == "-h") {
      std::cout << "FrameViz External App Backend (C++)\n\n"
                << "Usage:\n"
                << "  frameviz_external_backend [--ui-port 9621] [--viewer-name main_viewer]"
                   " [--frameviz-url ws://127.0.0.1:9527] [--host-headless 1]\n\n"
                << "Options:\n"
                << "  --ui-port PORT       UI command WebSocket port (default: 9621)\n"
                << "  --viewer-name NAME   FrameViz viewer name (default: main_viewer)\n"
                << "  --frameviz-url URL   FrameViz Host websocket URL (default: ws://127.0.0.1:9527)\n"
                << "  --host-headless 0|1  Auto-start Host in headless mode (default: 1)\n";
      return 0;
    }
  }

  std::signal(SIGINT, signal_handler);
  std::signal(SIGTERM, signal_handler);

  ExternalBackend backend(ui_port, viewer_name, frameviz_url, host_headless);
  if (!backend.start()) {
    return 1;
  }

  backend.run();
  backend.stop();
  std::cout << "[Backend] Stopped" << std::endl;
  return 0;
}
