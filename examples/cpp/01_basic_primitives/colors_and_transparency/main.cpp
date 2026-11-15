/**
 * FrameViz C++ Example - Colors and Transparency
 *
 * 展示颜色与透明度设置。
 *
 * 对应 Python: examples/python/01_basic_primitives/use_colors_and_transparency.py
 */

#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <iostream>
#include <thread>
#include <chrono>
#include <cmath>

using namespace frameviz;

int main() {
    std::cout << "FrameViz C++ - Colors and Transparency\n" << std::endl;

    const frameviz::example::Interrupt interrupt;
    auto viz = Viz::open();
    std::cout << "✓ Connected to FrameViz\n" << std::endl;

    viz->addPlane(10.0f, 10.0f, {0, 0, 0}, {0, 0, 0, 1},
                  {0.3f, 0.3f, 0.3f, 0.5f});
    viz->addAxes(1.0f);

    // 1. RGB颜色 (不透明)
    std::cout << "[1] Creating objects with RGB colors..." << std::endl;
    viz->addBox({1, 1, 1}, {-2, 0, 0.5f}, {0, 0, 0, 1}, {1, 0, 0});      // 红色
    viz->addSphere(0.5f, {0, 0, 0.5f}, {0, 0, 0, 1}, {0, 1, 0});         // 绿色
    viz->addCylinder(0.3f, 1.2f, {2, 0, 0.6f}, {0, 0, 0, 1}, {0, 0, 1}); // 蓝色

    // 2. RGBA颜色 (带透明度)
    std::cout << "[2] Creating transparent objects..." << std::endl;
    auto box1 = viz->addBox({1.5f, 1.5f, 0.2f}, {-1, 2, 0.5f},
                            {0, 0, 0, 1}, {1, 0, 0, 0.3f});
    auto box2 = viz->addBox({1.5f, 1.5f, 0.2f}, {0, 2, 0.8f},
                            {0, 0, 0, 1}, {0, 1, 0, 0.5f});
    auto box3 = viz->addBox({1.5f, 1.5f, 0.2f}, {1, 2, 1.1f},
                            {0, 0, 0, 1}, {0, 0, 1, 0.7f});

    // 3. 灰度颜色
    std::cout << "[3] Creating objects with grayscale colors..." << std::endl;
    viz->addSphere(0.3f, {-2, -2, 0.3f}, {0, 0, 0, 1}, {0, 0, 0});
    viz->addSphere(0.3f, {-1, -2, 0.3f}, {0, 0, 0, 1}, {0.5f, 0.5f, 0.5f});
    viz->addSphere(0.3f, {0, -2, 0.3f}, {0, 0, 0, 1}, {1, 1, 1});

    viz->setCameraPose({6, 6, 4}, {0, 0, 0.5f}, {0, 0, 1});

    std::cout << "\n" << std::string(60, '=') << std::endl;
    std::cout << "✓ Demonstrating dynamic color changes..." << std::endl;
    std::cout << "  Watch the transparent boxes change color!" << std::endl;
    std::cout << "  Press Ctrl+C to exit" << std::endl;
    std::cout << std::string(60, '=') << std::endl;

    // 4. 动态改变颜色
    for (int i = 0; i < 100 && !interrupt.requested(); ++i) {
        float t = i * 0.1f;
        float r = 0.5f + 0.5f * std::sin(t);
        float g = 0.5f + 0.5f * std::sin(t + 2.094f);
        float b = 0.5f + 0.5f * std::sin(t + 4.189f);

        viz->setColor(box1, {r, 0.0f, 0.0f, 0.3f});
        viz->setColor(box2, {0.0f, g, 0.0f, 0.5f});
        viz->setColor(box3, {0.0f, 0.0f, b, 0.7f});

        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    viz->close();
    if (interrupt.requested()) return 130;
    std::cout << "\n✓ Demo completed" << std::endl;
    return 0;
}
