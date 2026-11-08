/**
 * FrameViz C++ Example - Resource Cleanup Check
 *
 * 对应 Python: examples/python/01_basic_primitives/use_resource_cleanup.py
 */

#include <frameviz/viz.hpp>
#include <iostream>
#include <vector>
#include <random>
#include <thread>
#include <chrono>

using namespace frameviz;

int main() {
    std::cout << "==================================================" << std::endl;
    std::cout << "FrameViz Resource Cleanup Check" << std::endl;
    std::cout << "==================================================" << std::endl;

    auto viz = Viz::open();

    const int point_count = 50000;
    std::vector<float> positions(point_count * 3);
    std::vector<Color> colors;
    colors.reserve(point_count);

    std::mt19937 gen(0);
    std::normal_distribution<float> dist(0.0f, 1.0f);
    std::uniform_int_distribution<int> color_dist(0, 255);

    for (int i = 0; i < point_count; ++i) {
        positions[i * 3 + 0] = dist(gen);
        positions[i * 3 + 1] = dist(gen);
        positions[i * 3 + 2] = 0.2f * dist(gen);

        const float r = static_cast<float>(color_dist(gen)) / 255.0f;
        const float g = static_cast<float>(color_dist(gen)) / 255.0f;
        const float b = static_cast<float>(color_dist(gen)) / 255.0f;
        colors.push_back({r, g, b});
    }

    viz->addText2D("Resource cleanup check: see renderer.info.memory", 12, 12, 14, {1, 1, 1});

    std::cout << "Start create/remove cycles..." << std::endl;
    for (int i = 0; i < 5; ++i) {
        std::cout << "  [Cycle " << (i + 1) << "/5] add -> remove" << std::endl;
        std::vector<Handle> handles;
        handles.push_back(viz->addBox({1, 1, 1}, {0, 0, 0.5f}, {0, 0, 0, 1}, {1, 0, 0}));
        handles.push_back(viz->addSphere(0.5f, {2, 0, 0.5f}, {0, 0, 0, 1}, {0, 0, 1}));
        handles.push_back(viz->addPoints(positions, colors, 2.0f));

        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        viz->removeObjects(handles);
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }

    std::cout << "Cycles complete. Check renderer.info.memory in viewer." << std::endl;
    std::cout << "\nPress Enter to clear scene + overlays..." << std::endl;
    std::cin.get();
    viz->clear();
    std::cout << "Cleared. The 2D overlay text should be gone." << std::endl;
    std::cout << "\nPress Enter to exit..." << std::endl;
    std::cin.get();

    viz->close();
    return 0;
}
