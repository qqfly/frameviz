/**
 * FrameViz C++ Example - Picking Demo
 *
 * 对应 Python: examples/python/03_interaction/use_picking_demo.py
 */

#include <frameviz/viz.hpp>
#include <iostream>
#include <unordered_map>
#include <atomic>
#include <thread>
#include <chrono>

using namespace frameviz;

std::atomic<bool> running{true};

void eventLoop(Viz &viz) {
    while (running) {
        viz.pollEvents();
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
}

int main() {
    std::cout << "==================================================" << std::endl;
    std::cout << "FrameViz Picking Demo" << std::endl;
    std::cout << "==================================================" << std::endl;

    auto viz = Viz::open();

    std::unordered_map<std::string, Color> base_colors;

    auto box = viz->addBox({0.8f, 0.8f, 0.8f}, {-2, 0, 0.4f}, {0, 0, 0, 1},
                           {0.9f, 0.2f, 0.2f});
    base_colors[box] = {0.9f, 0.2f, 0.2f};

    auto sphere =
        viz->addSphere(0.5f, {0, 0, 0.5f}, {0, 0, 0, 1}, {0.2f, 0.9f, 0.2f});
    base_colors[sphere] = {0.2f, 0.9f, 0.2f};

    auto cyl = viz->addCylinder(0.3f, 1.0f, {2, 0, 0.5f}, {0, 0, 0, 1},
                                {0.2f, 0.2f, 0.9f});
    base_colors[cyl] = {0.2f, 0.2f, 0.9f};

    viz->setCameraPose({5, 5, 3}, {0, 0, 0.5f}, {0, 0, 1});

    json pick_config = {{"enabled", true}, {"mode", "object"}, {"button", 0}};
    viz->setPickConfig(pick_config);

    std::string current_handle;

    viz->onEvent("picked", [&](const json &evt) {
        std::string hit_type = evt.value("hit_type", "");
        std::string handle = evt.value("handle", "");

        if (!current_handle.empty() && base_colors.count(current_handle)) {
            viz->setColor(current_handle, base_colors[current_handle]);
        }

        if (hit_type == "none" || handle.empty()) {
            current_handle.clear();
            return;
        }

        if (base_colors.count(handle)) {
            current_handle = handle;
            viz->setColor(handle, {1.0f, 1.0f, 0.2f});
            std::cout << "Picked handle: " << handle << std::endl;
        }
    });

    std::thread event_thread(eventLoop, std::ref(*viz));

    std::cout << "Click objects to highlight. Press Enter to exit..." << std::endl;
    std::cin.get();

    running = false;
    if (event_thread.joinable()) {
        event_thread.join();
    }

    viz->close();
    return 0;
}
