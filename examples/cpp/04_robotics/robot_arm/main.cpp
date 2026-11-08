/**
 * FrameViz C++ Example - Simple Robot Arm
 *
 * 对应 Python: examples/python/04_robotics/use_robot_arm.py (简化版本)
 */

#include <frameviz/viz.hpp>
#include <iostream>
#include <vector>
#include <cmath>
#include <thread>
#include <chrono>

using namespace frameviz;

static Quat quatFromYaw(float yaw) {
    float half = yaw * 0.5f;
    return {0.0f, 0.0f, std::sin(half), std::cos(half)};
}

int main() {
    std::cout << "==================================================" << std::endl;
    std::cout << "FrameViz Robot Arm (Simplified)" << std::endl;
    std::cout << "==================================================" << std::endl;

    auto viz = Viz::open();

    viz->addPlane(6.0f, 6.0f, {0, 0, 0}, {0, 0, 0, 1},
                  {0.3f, 0.3f, 0.3f, 0.5f});
    viz->addAxes(1.0f);

    const float L1 = 0.8f;
    const float L2 = 0.7f;
    const float L3 = 0.6f;

    auto link1 = viz->addBox({L1, 0.1f, 0.1f}, {L1 * 0.5f, 0, 0.1f},
                             {0, 0, 0, 1}, {0.9f, 0.2f, 0.2f});
    auto link2 = viz->addBox({L2, 0.1f, 0.1f}, {L1 + L2 * 0.5f, 0, 0.1f},
                             {0, 0, 0, 1}, {0.2f, 0.9f, 0.2f});
    auto link3 =
        viz->addBox({L3, 0.1f, 0.1f}, {L1 + L2 + L3 * 0.5f, 0, 0.1f},
                    {0, 0, 0, 1}, {0.2f, 0.2f, 0.9f});

    viz->setCameraPose({4, 4, 3}, {1.2f, 0, 0.1f}, {0, 0, 1});
    viz->addText2D("Simple planar arm animation", 12, 12, 14, {1, 1, 1});

    for (int i = 0; i < 200; ++i) {
        float t = i * 0.05f;
        float a1 = 0.6f * std::sin(t);
        float a2 = 0.8f * std::sin(t * 0.7f + 0.5f);
        float a3 = 0.6f * std::sin(t * 0.9f + 1.2f);

        float theta1 = a1;
        float theta2 = a1 + a2;
        float theta3 = a1 + a2 + a3;

        float x1 = (L1 * 0.5f) * std::cos(theta1);
        float y1 = (L1 * 0.5f) * std::sin(theta1);

        float x2 = L1 * std::cos(theta1) + (L2 * 0.5f) * std::cos(theta2);
        float y2 = L1 * std::sin(theta1) + (L2 * 0.5f) * std::sin(theta2);

        float x3 = L1 * std::cos(theta1) + L2 * std::cos(theta2) +
                   (L3 * 0.5f) * std::cos(theta3);
        float y3 = L1 * std::sin(theta1) + L2 * std::sin(theta2) +
                   (L3 * 0.5f) * std::sin(theta3);

        viz->setTransform(link1, {x1, y1, 0.1f}, quatFromYaw(theta1));
        viz->setTransform(link2, {x2, y2, 0.1f}, quatFromYaw(theta2));
        viz->setTransform(link3, {x3, y3, 0.1f}, quatFromYaw(theta3));

        std::this_thread::sleep_for(std::chrono::milliseconds(30));
    }

    std::cout << "Animation complete. Press Enter to exit..." << std::endl;
    std::cin.get();

    viz->close();
    return 0;
}
