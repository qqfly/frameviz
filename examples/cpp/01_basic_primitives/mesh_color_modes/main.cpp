// Compare a uniform color and one color per triangle.
#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <iostream>

using namespace frameviz;

int main() {
    const frameviz::example::Interrupt interrupt;
    auto viz = Viz::open();
    const std::vector<float> vertices = {-0.5f, 0, 0, 0.5f, 0, 0, 0.5f, 0, 1, -0.5f, 0, 1};
    const std::vector<uint32_t> faces = {0, 1, 2, 0, 2, 3};
    SceneNodeOptions left, right;
    left.pose = RigidPose{{-0.7f, 0, 0}};
    right.pose = RigidPose{{0.7f, 0, 0}};
    viz->addMesh(vertices, faces, FacesFormat::TRI, {0.275f, 0.51f, 0.706f},
                 {}, std::nullopt, false, true, left);
    viz->addMesh(vertices, faces, FacesFormat::TRI, {1, 1, 1},
                 {{0.1f, 0.5f, 0.8f}, {0.9f, 0.4f, 0.1f}}, std::nullopt, false, true, right);
    viz->setCameraPose({2, -5, 2}, {0, 0, 0.5f}, {0, 0, 1});
    std::cout << "Uniform color on the left, per-face colors on the right. Enter to exit.\n";
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->close();
}
