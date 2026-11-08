/**
 * @file main.cpp
 * @brief URDF Robot Backend main entry point
 *
 * This C++ backend connects to EXISTING FrameViz views announced by the
 * Tauri frontend, using high-level API matching the Python backend.
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#include <frameviz/viz.hpp>
#include <frameviz/client.hpp>
#include <frameviz/discovery.hpp>
#include "urdf_robot/robot_visualizer.hpp"
#include "urdf_robot/ui_server.hpp"
#include "urdf_robot/asset_server.hpp"

#include <iostream>
#include <filesystem>
#include <csignal>
#include <atomic>
#include <mutex>
#include <thread>
#include <optional>

namespace fs = std::filesystem;
using json = nlohmann::json;

// Global flag for graceful shutdown
static std::atomic<bool> g_running{true};

// Environment variables for configuration
static bool g_resetCamera = []() {
    const char* env = std::getenv("URDF_ROBOT_RESET_CAMERA");
    return env && std::string(env) == "1";
}();

void signalHandler(int /*signal*/) {
    std::cout << "\n[Backend] Shutting down..." << std::endl;
    g_running.store(false);
}

struct Config {
    fs::path model_path;
    int ui_port = 9620;
    int asset_port = 8081;
};

void printUsage(const char* program) {
    std::cout << "URDF Robot Backend - C++ implementation\n\n";
    std::cout << "Usage:\n";
    std::cout << "    " << program << " --path /path/to/sample_robot\n\n";
    std::cout << "Options:\n";
    std::cout << "    --path PATH    Path to sample_robot directory containing meshes/\n";
    std::cout << "    --ui-port PORT WebSocket port for UI (default: 9620)\n";
    std::cout << "    --asset-port PORT HTTP port for assets (default: 8081)\n";
    std::cout << "    --help         Show this help message\n";
}

bool parseArgs(int argc, char* argv[], Config& config) {
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];

        if (arg == "--help" || arg == "-h") {
            printUsage(argv[0]);
            return false;
        } else if (arg == "--path" && i + 1 < argc) {
            config.model_path = argv[++i];
        } else if (arg == "--ui-port" && i + 1 < argc) {
            config.ui_port = std::stoi(argv[++i]);
        } else if (arg == "--asset-port" && i + 1 < argc) {
            config.asset_port = std::stoi(argv[++i]);
        } else {
            std::cerr << "[Backend] Unknown argument: " << arg << std::endl;
            printUsage(argv[0]);
            return false;
        }
    }

    if (config.model_path.empty()) {
        std::cerr << "[Backend] Error: --path argument is required\n" << std::endl;
        printUsage(argv[0]);
        return false;
    }

    return true;
}

bool validateModelPath(const fs::path& model_path) {
    if (!fs::exists(model_path)) {
        std::cerr << "[Backend] Error: Model path does not exist: " << model_path << std::endl;
        return false;
    }

    auto meshes_dir = model_path / "meshes";
    if (!fs::exists(meshes_dir)) {
        std::cerr << "[Backend] Error: meshes/ directory not found in: " << model_path << std::endl;
        return false;
    }

    auto visual_dir = meshes_dir / "visual";
    if (!fs::exists(visual_dir)) {
        std::cerr << "[Backend] Error: visual meshes not found: " << visual_dir << std::endl;
        return false;
    }

    return true;
}

// Visualizer state for a single viewer
struct VisualizerState {
    std::string role;
    std::string mesh_base_url;
    std::string mesh_extension;
    std::optional<std::array<float, 4>> color;  // RGBA

    std::string view_id;
    std::string scene_id;
    std::shared_ptr<frameviz::Viz> viz;
    std::shared_ptr<urdf_robot::RobotVisualizer> visualizer;
    bool initialized = false;
};

int main(int argc, char* argv[]) {
    // Parse command line arguments
    Config config;
    if (!parseArgs(argc, argv, config)) {
        return 1;
    }

    // Validate model path
    config.model_path = fs::absolute(config.model_path);
    if (!validateModelPath(config.model_path)) {
        return 1;
    }

    std::cout << "[Backend] Using model path: " << config.model_path << std::endl;

    // Set up signal handler for graceful shutdown
    std::signal(SIGINT, signalHandler);
    std::signal(SIGTERM, signalHandler);

    // Start asset server
    urdf_robot::AssetServer asset_server(config.model_path, config.asset_port);
    if (!asset_server.start()) {
        std::cerr << "[Backend] Failed to start asset server" << std::endl;
        return 1;
    }

    // Build mesh URLs
    std::string visual_url = asset_server.baseUrl() + "/meshes/visual";
    std::string collision_url = asset_server.baseUrl() + "/meshes/collision";

    std::cout << "[Backend] Visual mesh URL: " << visual_url << std::endl;

    // Check FrameViz Host availability
    std::cout << "[Backend] Connecting to FrameViz Host..." << std::endl;
    std::string ws_url = "ws://127.0.0.1:9527";
    try {
        if (auto discovered = frameviz::getWsUrlFromDiscovery(); discovered.has_value() && !discovered->empty()) {
            ws_url = *discovered;
        }
        frameviz::FrameVizClient probe(ws_url);
        probe.connect(std::chrono::seconds(1));
        probe.close();
        std::cout << "[Backend] Connected to FrameViz Host" << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "[Backend] Failed to connect: " << e.what() << std::endl;
        std::cerr << "[Backend] Make sure the Tauri host is running:" << std::endl;
        std::cerr << "[Backend]   pnpm -C examples/apps/urdf_robot tauri:dev" << std::endl;
        return 1;
    }

    // Current joint angles
    urdf_robot::JointAngles current_angles = {0, 0, 0, 0, 0, 0};

    // Visualizer states for each viewer
    VisualizerState visual_state;
    visual_state.role = "main";
    visual_state.mesh_base_url = visual_url;
    visual_state.mesh_extension = "dae";

    VisualizerState collision_state;
    collision_state.role = "collision";
    collision_state.mesh_base_url = collision_url;
    collision_state.mesh_extension = "stl";
    collision_state.color = std::array<float, 4>{{0.9f, 0.3f, 0.2f, 0.4f}};  // Semi-transparent red

    // Start UI server
    urdf_robot::UIServer ui_server(config.ui_port);
    std::optional<std::string> target_main_view_id;
    std::optional<std::string> target_collision_view_id;
    std::mutex target_views_mutex;

    // Set up joint update callback
    ui_server.onJointUpdate([&](const urdf_robot::JointAngles& angles) {
        current_angles = angles;

        // Update both visualizers using high-level API
        if (visual_state.visualizer) {
            visual_state.visualizer->setJointAngles(angles);
        }
        if (collision_state.visualizer) {
            collision_state.visualizer->setJointAngles(angles);
        }

        // Broadcast state update to UI
        ui_server.broadcastState(angles);
    });

    ui_server.onViewIdsUpdate([&](
        const std::optional<std::string>& main_view_id,
        const std::optional<std::string>& collision_view_id) {
        std::lock_guard<std::mutex> lock(target_views_mutex);
        target_main_view_id = main_view_id;
        target_collision_view_id = collision_view_id;
        std::cout << "[Backend] Updated targets: main="
                  << (target_main_view_id ? *target_main_view_id : "none")
                  << ", collision="
                  << (target_collision_view_id ? *target_collision_view_id : "none")
                  << std::endl;
    });

    if (!ui_server.start()) {
        std::cerr << "[Backend] Failed to start UI server" << std::endl;
        return 1;
    }

    std::cout << "[Backend] Waiting for frontend to publish view_ids..." << std::endl;
    std::cout << "[Backend] Start the Tauri app: pnpm -C examples/apps/urdf_robot tauri:dev" << std::endl;

    // Main loop: poll for viewers and handle updates
    while (g_running.load()) {
        try {
            std::optional<std::string> main_target;
            std::optional<std::string> collision_target;
            {
                std::lock_guard<std::mutex> lock(target_views_mutex);
                main_target = target_main_view_id;
                collision_target = target_collision_view_id;
            }

            auto reconcile_state = [&](VisualizerState& state, const std::optional<std::string>& target_view_id) {
                if (!target_view_id.has_value() || target_view_id->empty()) {
                    if (state.viz) {
                        state.viz->close();
                    }
                    state.viz.reset();
                    state.visualizer.reset();
                    state.initialized = false;
                    state.view_id.clear();
                    state.scene_id.clear();
                    return;
                }
                if (state.initialized && state.view_id == *target_view_id) {
                    return;
                }
                if (state.viz) {
                    state.viz->close();
                }
                state.viz.reset();
                state.visualizer.reset();
                state.initialized = false;
                state.view_id.clear();
                state.scene_id.clear();

                auto viz_unique = frameviz::Viz::connect(
                    ws_url, *target_view_id, std::chrono::seconds(1));
                state.view_id = viz_unique->viewId();
                state.scene_id = viz_unique->sceneId();
                state.viz = std::shared_ptr<frameviz::Viz>(std::move(viz_unique));

                std::cout << "[Backend] Initializing view role=" << state.role
                          << " target=" << *target_view_id
                          << " (view_id=" << state.view_id
                          << ", scene_id=" << state.scene_id << ")" << std::endl;

                state.visualizer = std::make_shared<urdf_robot::RobotVisualizer>(
                    state.viz,
                    state.mesh_base_url,
                    state.mesh_extension,
                    state.color
                );
                state.visualizer->loadMeshes();
                state.viz->setRenderMode("quality");
                if (g_resetCamera) {
                    std::cout << "[Backend] Resetting camera" << std::endl;
                    state.viz->setCameraPose(
                        {2.0f, -2.0f, 1.5f},
                        {0.3f, 0.0f, 0.5f},
                        {0.0f, 0.0f, 1.0f}
                    );
                }
                state.visualizer->setJointAngles(current_angles);
                state.initialized = true;
                std::cout << "[Backend] View " << state.role << " ready" << std::endl;
            };

            reconcile_state(visual_state, main_target);
            reconcile_state(collision_state, collision_target);

        } catch (const std::exception& e) {
            std::cerr << "[Backend] Error polling views: " << e.what() << std::endl;
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }

    // Cleanup
    std::cout << "[Backend] Cleaning up..." << std::endl;
    ui_server.stop();
    asset_server.stop();
    if (visual_state.viz) {
        visual_state.viz->close();
    }
    if (collision_state.viz) {
        collision_state.viz->close();
    }

    std::cout << "[Backend] Done." << std::endl;
    return 0;
}
