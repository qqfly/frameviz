// Move a child between frames and inspect local and world poses.
#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <iostream>

using namespace frameviz;

int main() {
    const frameviz::example::Interrupt interrupt;
    auto viz = Viz::open();
    SceneNodeOptions left, right;
    left.name = "Left frame";
    left.pose = RigidPose{{-1, 0, 0}};
    right.name = "Right frame";
    right.pose = RigidPose{{1, 0, 0}};
    const auto first = viz->addNode(left);
    const auto second = viz->addNode(right);

    for (const auto &parent : {first, second}) {
        SceneNodeOptions axes;
        axes.parent = parent;
        viz->addAxes(0.4f, 0.02f, {0, 0, 0}, {0, 0, 0, 1}, axes);
    }
    SceneNodeOptions child;
    child.parent = first;
    child.name = "Box";
    child.tags = {{"example", "reparent"}};
    const auto box = viz->addBox({0.5f, 0.5f, 0.5f}, {0, 0, 0.25f}, {0, 0, 0, 1},
                                 {1, 0.65f, 0}, child);
    SceneNodeOptions markerOptions;
    markerOptions.parent = box;
    const auto marker = viz->addSphere(0.1f, {0, 0, 0.5f}, {0, 0, 0, 1}, {0, 0, 1}, markerOptions);
    viz->setCameraPose({3, -5, 3}, {0, 0, 0.3f}, {0, 0, 1});

    std::cout << "Enter to reparent while preserving the world pose.\n";
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->setParent(box, second);
    std::cout << "Local: " << json(viz->getTransform(box).pos)
              << ", world: " << json(viz->getTransform(box, TransformSpace::World).pos) << '\n';
    std::cout << "Enter to specify a new local pose in the right frame.\n";
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->setParent(box, second, RigidPose{{0, 0, 0.25f}});
    viz->setGeometryScale(box, {2, 1, 1});
    std::cout << "Marker world position: " << json(viz->getTransform(marker, TransformSpace::World).pos) << '\n';
    const auto state = viz->getDisplayState(true);
    for (const auto &object : state.at("objects")) {
        std::cout << object.at("name") << ' ' << object.at("parent") << ' '
                  << object.at("world_transform").at("position") << ' '
                  << object.value("world_bounds", json{}) << '\n';
    }
    std::cout << "The box is wider; the marker kept its local offset. Enter to exit.\n";
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->close();
}
