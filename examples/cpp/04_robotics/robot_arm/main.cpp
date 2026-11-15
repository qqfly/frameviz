// Animate three links by updating local joint poses in a scene tree.
#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <chrono>
#include <cmath>
#include <iostream>
#include <thread>

using namespace frameviz;

int main() {
    const frameviz::example::Interrupt interrupt;
    auto viz = Viz::open();
    const std::array<float, 3> lengths{0.8f, 0.7f, 0.6f};
    const std::array<Vec3, 3> offsets{{{0, 0, 0.1f}, {lengths[0], 0, 0}, {lengths[1], 0, 0}}};
    const std::array<Color, 3> colors{{{0.9f, 0.2f, 0.2f}, {0.2f, 0.9f, 0.2f}, {0.2f, 0.2f, 0.9f}}};
    std::vector<Handle> joints;
    viz->addPlane(6, 6, {0, 0, 0}, {0, 0, 0, 1}, {0.3f, 0.3f, 0.3f, 0.5f});
    viz->addAxes(1);
    for (size_t i = 0; i < lengths.size(); ++i) {
        SceneNodeOptions joint;
        if (!joints.empty()) joint.parent = joints.back();
        joint.name = "Joint " + std::to_string(i + 1);
        joint.pose = RigidPose{offsets[i]};
        joints.push_back(viz->addNode(joint));
        SceneNodeOptions link;
        link.parent = joints.back();
        link.name = "Link " + std::to_string(i + 1);
        viz->addBox({lengths[i], 0.1f, 0.1f}, {lengths[i] / 2, 0, 0},
                    {0, 0, 0, 1}, colors[i], link);
    }

    viz->setCameraPose({4, 4, 3}, {1.2f, 0, 0.1f}, {0, 0, 1});
    viz->addText2D("Planar arm - local joint poses", 12, 12);
    for (int step = 0; step < 200 && !interrupt.requested(); ++step) {
        const auto t = step * 0.05f;
        const std::array<float, 3> angles{0.6f * std::sin(t), 0.8f * std::sin(t * 0.7f + 0.5f),
                                           0.6f * std::sin(t * 0.9f + 1.2f)};
        std::vector<TransformItem> updates;
        for (size_t i = 0; i < joints.size(); ++i) {
            const auto half = angles[i] / 2;
            Pose pose;
            pose.pos = offsets[i];
            pose.quat = {0, 0, std::sin(half), std::cos(half)};
            updates.push_back({joints[i], pose});
        }
        viz->setObjectTransforms(updates);
        std::this_thread::sleep_for(std::chrono::milliseconds(30));
    }
    std::cout << "Animation complete. Enter to exit.\n";
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->close();
}
