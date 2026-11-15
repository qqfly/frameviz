/**
 * FrameViz C++ Example - Hello World
 *
 * 最简单的 FrameViz 示例：连接、绘制基础图元、等待退出。
 *
 * 对应 Python: examples/python/01_basic_primitives/hello_world.py
 */

#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <iostream>

using namespace frameviz;

int main() {
    try {
        std::cout << "FrameViz C++ - Hello World\n" << std::endl;

        // 1. 连接到 FrameViz Host
        std::cout << "[1] Connecting to FrameViz..." << std::endl;
        const frameviz::example::Interrupt interrupt;
        auto viz = Viz::open();
        std::cout << "    ✓ Connected! scene=" << viz->sceneId()
                  << ", view=" << viz->viewId() << "\n" << std::endl;

        // 2. 绘制基础图元
        std::cout << "[2] Drawing primitives..." << std::endl;

        // 添加地面平面
        viz->addPlane(10.0f, 10.0f, {0, 0, 0}, {0, 0, 0, 1},
                      {0.3f, 0.3f, 0.3f, 0.5f});

        // 添加坐标轴
        viz->addAxes(1.0f);

        // 添加立方体 (红色)
        viz->addBox({1, 1, 1}, {0, 0, 0.5f}, {0, 0, 0, 1}, {1, 0, 0});

        // 添加球体 (蓝色)
        viz->addSphere(0.3f, {2, 0, 0.3f}, {0, 0, 0, 1}, {0, 0, 1});

        // 添加圆柱 (绿色)
        viz->addCylinder(0.2f, 1.0f, {-2, 0, 0.5f}, {0, 0, 0, 1}, {0, 1, 0});

        // 添加箭头 (黄色)
        viz->addArrow({1, 2, 0}, {1, 2, 1.5f}, 0.05f, {1, 1, 0});
        viz->addCone(0.35f, 0.8f, {-1.8f, 1.5f, 0.4f}, {0, 0, 0, 1}, {1, 0.65f, 0});

        std::cout << "    ✓ Primitives created\n" << std::endl;

        // 3. 设置相机视角
        std::cout << "[3] Setting camera pose..." << std::endl;
        viz->setCameraPose({5, 5, 3}, {0, 0, 0.5f}, {0, 0, 1});
        std::cout << "    ✓ Camera set\n" << std::endl;

        // 4. 添加3D文本标签 (白色)
        viz->addText3D("Hello FrameViz!", {0, 0, 2}, 20, {1, 1, 1});

        std::cout << "\n" << std::string(60, '=') << std::endl;
        std::cout << "✓ Scene created successfully!" << std::endl;
        std::cout << "\nPress Enter to exit..." << std::endl;
        std::cout << std::string(60, '=') << std::endl;

        // 等待用户按键
        if (!interrupt.waitForEnter(*viz)) return 130;

        viz->close();
        std::cout << "\n✓ Goodbye!" << std::endl;

        return 0;
    } catch (const std::exception& e) {
        std::cerr << "\n❌ Error: " << e.what() << std::endl;
        return 1;
    }
}
