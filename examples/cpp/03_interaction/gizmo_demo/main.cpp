/**
 * FrameViz C++ Example - Gizmo Demo
 *
 * 展示 Gizmo 交互式变换控制。
 *
 * 对应 Python: examples/python/03_interaction/use_gizmo_demo.py
 */

#include <frameviz/viz.hpp>
#include <iostream>
#include <atomic>
#include <thread>
#include <chrono>
#include <unordered_map>

using namespace frameviz;

std::atomic<bool> running{true};

void eventLoop(Viz &viz)
{
    while (running) {
        viz.pollEvents();
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
}

int main()
{
    std::cout << "FrameViz - Gizmo Demo\n" << std::endl;

    auto viz = Viz::open();
    std::cout << "✓ Connected to FrameViz\n" << std::endl;

    // 1. 创建场景对象
    std::cout << "[1] Creating scene objects..." << std::endl;
    viz->addPlane(6.0f, 6.0f, {0, 0, 0}, {0, 0, 0, 1},
                  {0.3f, 0.3f, 0.3f, 0.5f});
    viz->addAxes(1.0f);

    std::unordered_map<std::string, std::string> object_names;

    auto red_box = viz->addBox({0.8f, 0.8f, 0.8f}, {-2, 0, 0.4f},
                               {0, 0, 0, 1}, {0.9f, 0.2f, 0.2f});
    object_names[red_box] = "红色立方体";

    auto green_sphere =
        viz->addSphere(0.5f, {0, 0, 0.5f}, {0, 0, 0, 1}, {0.2f, 0.9f, 0.2f});
    object_names[green_sphere] = "绿色球体";

    auto blue_cylinder =
        viz->addCylinder(0.3f, 1.0f, {2, 0, 0.5f}, {0, 0, 0, 1},
                         {0.2f, 0.2f, 0.9f});
    object_names[blue_cylinder] = "蓝色圆柱";

    std::cout << "    ✓ Created objects\n" << std::endl;

    // 2. 设置相机
    viz->setCameraPose({5, 5, 3}, {0, 0, 0.5f}, {0, 0, 1});

    // 3. 启用 picking (使用右键 - button 2)
    std::cout << "[2] Enabling picking..." << std::endl;
    json pick_config = {{"enabled", true}, {"mode", "object"}, {"button", 2}};
    viz->setPickConfig(pick_config);
    std::cout << "    ✓ Picking enabled\n" << std::endl;

    // 4. 启动事件循环线程（必须在 attachGizmo 之前启动）
    std::cout << "[3] Starting event loop..." << std::endl;
    std::thread event_thread(eventLoop, std::ref(*viz));

    // 等待一小段时间确保事件循环已启动
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    std::cout << "    ✓ Event loop started\n" << std::endl;

    // 5. 注册事件回调（Picked + Key + Transformed）
    std::cout << "[4] Registering event callbacks..." << std::endl;

    std::string current_handle;
    int current_mask = 0x3F; // All DOFs enabled (Tx|Ty|Tz|Rx|Ry|Rz)
    std::string current_scale_mode = "world";

    viz->onEvent("picked", [&](const json &evt) {
        std::string hit_type = evt.value("hit_type", "");
        std::string handle = evt.value("handle", "");

        if (hit_type == "none") {
            if (!current_handle.empty()) {
                viz->detachGizmo();
                std::cout << "    → Gizmo detached" << std::endl;
                current_handle.clear();
            }
            return;
        }

        if (!handle.empty() && object_names.count(handle)) {
            current_handle = handle;
            viz->attachGizmo(handle, current_mask, 0.6f,
                             current_scale_mode);
            std::cout << "    → Picked: " << object_names[handle]
                      << " (Gizmo attached, mask=0x"
                      << std::hex << current_mask << std::dec << ")"
                      << std::endl;
        }
    });

    viz->onEvent("key_down", [&](const json &evt) {
        std::string key = evt.value("key", "");
        int new_mask = current_mask;
        bool need_update = false;

        if (key == "t" || key == "T") {
            new_mask = 0x07; // 0b000111: Tx|Ty|Tz
            std::cout << "    → Mode: Translate only" << std::endl;
        } else if (key == "r" || key == "R") {
            new_mask = 0x38; // 0b111000: Rx|Ry|Rz
            std::cout << "    → Mode: Rotate only" << std::endl;
        } else if (key == "a" || key == "A") {
            new_mask = 0x3F; // All
            std::cout << "    → Mode: Combined (all)" << std::endl;
        } else if (key == "m" || key == "M") {
            current_scale_mode = (current_scale_mode == "screen") ? "world" : "screen";
            need_update = true;
            std::cout << "    → Scale Mode: " << current_scale_mode << std::endl;
        } else if (key == "x" || key == "X") {
            new_mask ^= (0x01 | 0x08); // Toggle Tx and Rx
            std::cout << "    → Mask: Toggle X axis" << std::endl;
        } else if (key == "y" || key == "Y") {
            new_mask ^= (0x02 | 0x10); // Toggle Ty and Ry
            std::cout << "    → Mask: Toggle Y axis" << std::endl;
        } else if (key == "z" || key == "Z") {
            new_mask ^= (0x04 | 0x20); // Toggle Tz and Rz
            std::cout << "    → Mask: Toggle Z axis" << std::endl;
        }

        if (new_mask != current_mask || need_update) {
            current_mask = new_mask;
            if (!current_handle.empty()) {
                viz->setGizmoMode(current_mask, std::nullopt, current_scale_mode);
            }
            std::cout << "    → Current mask: 0x" << std::hex << current_mask
                      << std::dec << " | scale: " << current_scale_mode
                      << std::endl;
        }
    });

    viz->onEvent("transformed", [](const json &evt) {
        std::string handle = evt.value("handle", "");
        auto pose = evt.value("pose", json::object());
        auto pos = pose.value("pos", std::vector<float>{0.0f, 0.0f, 0.0f});

        std::cout << "    → Object " << handle << " moved to: "
                  << "pos=(" << pos[0] << ", " << pos[1] << ", " << pos[2]
                  << ")" << std::endl;
    });

    std::cout << "    ✓ Callbacks registered\n" << std::endl;

    std::cout << "\n" << std::string(60, '=') << std::endl;
    std::cout << "✓ Right-Click an object to attach Gizmo" << std::endl;
    std::cout << "\n  Instructions:" << std::endl;
    std::cout << "  T - Translate only    R - Rotate only    A - All (combined)" << std::endl;
    std::cout << "  M - Toggle scale mode (screen/world)" << std::endl;
    std::cout << "  X/Y/Z - Toggle axis mask" << std::endl;
    std::cout << "\n  Press Enter to exit..." << std::endl;
    std::cout << std::string(60, '=') << std::endl;

    std::cin.get();

    // 停止事件循环
    running = false;
    if (event_thread.joinable()) {
        event_thread.join();
    }

    viz->detachGizmo();
    viz->close();
    std::cout << "\n✓ Closed" << std::endl;

    return 0;
}
