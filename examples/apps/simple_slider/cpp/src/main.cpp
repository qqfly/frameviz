#include <frameviz/business_auth.hpp>
#include <frameviz/viz.hpp>

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

struct AppState {
    frameviz::Vec3 pos{0.0f, 0.0f, 0.5f};
    frameviz::Quat quat{0.0f, 0.0f, 0.0f, 1.0f};
    std::array<float, 4> rgba{1.0f, 0.42f, 0.42f, 1.0f};

    std::string view_id;
    std::string scene_id;
    std::string box_handle;

    bool scene_ready = false;
    std::unique_ptr<frameviz::Viz> viz;
};

std::optional<frameviz::Vec3> parse_vec3(const json& value) {
    if (!value.is_array() || value.size() != 3) {
        return std::nullopt;
    }

    frameviz::Vec3 out{};
    for (size_t i = 0; i < 3; ++i) {
        if (!value[i].is_number()) {
            return std::nullopt;
        }
        out[i] = value[i].get<float>();
    }
    return out;
}

std::optional<frameviz::Quat> parse_quat(const json& value) {
    if (!value.is_array() || value.size() != 4) {
        return std::nullopt;
    }

    frameviz::Quat out{};
    for (size_t i = 0; i < 4; ++i) {
        if (!value[i].is_number()) {
            return std::nullopt;
        }
        out[i] = value[i].get<float>();
    }
    return out;
}

std::optional<std::array<float, 4>> parse_rgba(const json& value) {
    if (!value.is_array() || (value.size() != 3 && value.size() != 4)) {
        return std::nullopt;
    }

    std::array<float, 4> out{1.0f, 1.0f, 1.0f, 1.0f};
    for (size_t i = 0; i < value.size(); ++i) {
        if (!value[i].is_number()) {
            return std::nullopt;
        }
        out[i] = value[i].get<float>();
    }
    return out;
}

class SimpleSliderBackend {
public:
    explicit SimpleSliderBackend(int ui_port, std::string viewer_name, std::string frameviz_url)
        : ui_port_(ui_port),
          viewer_name_(std::move(viewer_name)),
          frameviz_url_(std::move(frameviz_url)) {
    }

    bool start() {
        ui_server_ = std::make_unique<ix::WebSocketServer>(ui_port_, "127.0.0.1");
        ui_server_->setOnClientMessageCallback(
            [this](std::shared_ptr<ix::ConnectionState> connection_state,
                   ix::WebSocket& webSocket,
                   const ix::WebSocketMessagePtr& msg) {
                if (!business_auth_.accept(webSocket, msg)) return;
                if (msg->type == ix::WebSocketMessageType::Open) {
                    std::cout << "[Backend] UI client connected from "
                              << connection_state->getRemoteIp() << std::endl;
                    broadcast_state();
                    return;
                }
                if (msg->type == ix::WebSocketMessageType::Close) {
                    std::cout << "[Backend] UI client disconnected" << std::endl;
                    return;
                }
                if (msg->type == ix::WebSocketMessageType::Error) {
                    std::cerr << "[Backend] UI WebSocket error: "
                              << msg->errorInfo.reason << std::endl;
                    return;
                }
                if (msg->type == ix::WebSocketMessageType::Message) {
                    handle_ui_message(msg->str);
                }
            }
        );

        auto listen_result = ui_server_->listen();
        if (!listen_result.first) {
            std::cerr << "[Backend] Failed to start UI server on port " << ui_port_
                      << ": " << listen_result.second << std::endl;
            return false;
        }

        ui_server_->start();
        std::cout << "[Backend] UI WebSocket listening on ws://127.0.0.1:"
                  << ui_port_ << std::endl;
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
        std::lock_guard<std::mutex> lock(state_mutex_);
        if (state_.viz) {
            try {
                state_.viz->close();
            } catch (...) {
            }
            state_.viz.reset();
        }
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
            const std::string view_id = args.value("view_id", "");
            const std::string scene_id = args.value("scene_id", "");

            if (!requested_name.empty() && requested_name != viewer_name_) {
                viewer_name_ = requested_name;
            }

            if (!view_id.empty() && (view_id != state_.view_id || !state_.scene_ready)) {
                std::cout << "[Backend] UI requested viewer bind: viewer_name=" << viewer_name_
                          << " view_id=" << view_id << " scene_id=" << scene_id << std::endl;
                bind_view_locked(view_id);
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
            state_.pos = {0.0f, 0.0f, 0.5f};
            state_.quat = {0.0f, 0.0f, 0.0f, 1.0f};
            state_.rgba = {1.0f, 0.42f, 0.42f, 1.0f};
            apply_pose_locked();
            apply_color_locked();
            broadcast_state_locked();
            return;
        }

        send_error("Unknown command: " + name);
    }

    void poll_viewer() {
        std::lock_guard<std::mutex> lock(state_mutex_);
        if (!state_.scene_ready || !state_.viz || state_.box_handle.empty()) {
            if (!state_.view_id.empty()) {
                bind_view_locked(state_.view_id);
                broadcast_state_locked();
            }
            return;
        }

        try {
            const bool alive = state_.viz->isObjectAlive(state_.box_handle);
            if (alive) {
                return;
            }
        } catch (...) {
        }

        state_.scene_ready = false;
        state_.box_handle.clear();
        state_.viz.reset();
        broadcast_state_locked();
    }

    void bind_view_locked(const std::string& view_id) {
        if (view_id.empty()) {
            return;
        }

        try {
            auto viz = frameviz::Viz::connect(
                frameviz_url_,
                view_id,
                std::chrono::seconds(2)
            );
            state_.viz = std::move(viz);
            state_.view_id = state_.viz->viewId();
            state_.scene_id = state_.viz->sceneId();
            rebuild_scene_locked();
        } catch (const std::exception& e) {
            state_.scene_ready = false;
            state_.box_handle.clear();
            state_.viz.reset();
            std::cerr << "[Backend] Failed to bind view_id=" << view_id
                      << ": " << e.what() << std::endl;
        }
    }

    void rebuild_scene_locked() {
        if (!state_.viz) {
            state_.scene_ready = false;
            return;
        }

        try {
            state_.viz->clear();
            state_.viz->addAxes(1.0f);
            state_.viz->addPlane(
                6.0f,
                6.0f,
                frameviz::Vec3{0.0f, 0.0f, 0.0f},
                frameviz::Quat{0.0f, 0.0f, 0.0f, 1.0f},
                frameviz::Color{0.3f, 0.3f, 0.3f, 0.5f}
            );

            state_.box_handle = state_.viz->addBox(
                frameviz::Vec3{1.0f, 1.0f, 1.0f},
                state_.pos,
                state_.quat,
                frameviz::Color{state_.rgba[0], state_.rgba[1], state_.rgba[2], state_.rgba[3]}
            );

            state_.scene_ready = true;
            std::cout << "[Backend] Scene initialized, box handle=" << state_.box_handle << std::endl;
        } catch (const std::exception& e) {
            state_.scene_ready = false;
            state_.box_handle.clear();
            std::cerr << "[Backend] Failed to initialize scene: " << e.what() << std::endl;
        }
    }

    void apply_pose_locked() {
        if (!state_.scene_ready || !state_.viz || state_.box_handle.empty()) {
            return;
        }

        try {
            state_.viz->setTransform(state_.box_handle, state_.pos, state_.quat);
        } catch (const std::exception& e) {
            std::cerr << "[Backend] setTransform failed: " << e.what() << std::endl;
        }
    }

    void apply_color_locked() {
        if (!state_.scene_ready || !state_.viz || state_.box_handle.empty()) {
            return;
        }

        try {
            state_.viz->setColor(
                state_.box_handle,
                frameviz::Color{state_.rgba[0], state_.rgba[1], state_.rgba[2], state_.rgba[3]}
            );
        } catch (const std::exception& e) {
            std::cerr << "[Backend] setColor failed: " << e.what() << std::endl;
        }
    }

    void send_error(const std::string& message) {
        json payload = {
            {"type", "error"},
            {"message", message},
        };
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
    frameviz::BusinessAuth business_auth_;
    std::unique_ptr<ix::WebSocketServer> ui_server_;

    std::mutex state_mutex_;
    AppState state_;
};

} // namespace

int main(int argc, char* argv[]) {
    int ui_port = 9621;
    std::string viewer_name = "simple_slider_viewer";
    std::string frameviz_url = "ws://127.0.0.1:9527";

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--ui-port" && i + 1 < argc) {
            ui_port = std::stoi(argv[++i]);
        } else if (arg == "--viewer-name" && i + 1 < argc) {
            viewer_name = argv[++i];
        } else if (arg == "--frameviz-url" && i + 1 < argc) {
            frameviz_url = argv[++i];
        } else if (arg == "--help" || arg == "-h") {
            std::cout << "Simple Slider C++ Backend\n\n"
                      << "Usage:\n"
                      << "  simple_slider_backend [--ui-port 9621] [--viewer-name simple_slider_viewer]"
                      << " [--frameviz-url ws://127.0.0.1:9527]\n\n"
                      << "Options:\n"
                      << "  --ui-port PORT       UI command WebSocket port (default: 9621)\n"
                      << "  --viewer-name NAME   FrameViz viewer name (default: simple_slider_viewer)\n"
                      << "  --frameviz-url URL   FrameViz Host WebSocket URL (default: ws://127.0.0.1:9527)\n";
            return 0;
        }
    }

    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    SimpleSliderBackend backend(ui_port, viewer_name, frameviz_url);
    if (!backend.start()) {
        return 1;
    }

    backend.run();
    backend.stop();

    std::cout << "[Backend] Stopped" << std::endl;
    return 0;
}
