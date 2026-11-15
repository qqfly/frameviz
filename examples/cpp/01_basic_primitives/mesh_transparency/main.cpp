// Compare mesh opacity, object edges and View-wide wireframe.
#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <iostream>

using namespace frameviz;

int main() {
    const frameviz::example::Interrupt interrupt;
    auto viz = Viz::open();
    const std::vector<float> vertices = {-0.4f, -0.4f, 0, 0.4f, -0.4f, 0, 0.4f, 0.4f, 0,
                                         -0.4f, 0.4f, 0, 0, 0, 0.85f};
    const std::vector<uint32_t> faces = {0, 1, 4, 1, 2, 4, 2, 3, 4, 3, 0, 4, 0, 3, 2, 0, 2, 1};
    for (int i = -1; i <= 1; ++i) {
        SceneNodeOptions node;
        node.pose = RigidPose{{static_cast<float>(i), 0, 0}};
        viz->addMesh(vertices, faces, FacesFormat::TRI, {0.275f, 0.51f, 0.706f},
                     {}, i == -1 ? 1.0f : 0.4f, i == 1, true, node);
    }
    viz->setCameraPose({3, -5, 3}, {0, 0, 0.4f}, {0, 0, 1});
    std::cout << "Opaque, translucent, then translucent with edges. Enter for View wireframe.\n";
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->setRenderMode("wireframe");
    std::cout << "All three are now in wireframe. Enter to exit.\n";
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->close();
}
