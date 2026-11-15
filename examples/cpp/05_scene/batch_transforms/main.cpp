// Move several boxes in one call. Press Enter at each step.
#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <iostream>

int main() {
    const frameviz::example::Interrupt interrupt;
    auto viz = frameviz::Viz::open();
    std::vector<frameviz::TransformItem> updates;
    for (const float x : {-0.5f, 0.0f, 0.5f}) {
        auto box = viz->addBox({0.25f, 0.25f, 0.25f}, {x, 0, 0.125f}, {0, 0, 0, 1}, {0, 0, 1});
        frameviz::Pose pose;
        pose.pos = {x, 0.5f, 0.125f};
        pose.quat = {0, 0, 0, 1}; // Identity rotation in xyzw order.
        updates.push_back({box, pose});
    }
    std::cout << "Press Enter to move all three boxes.\n";
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->setObjectTransforms(updates);
    std::cout << "Press Enter to exit.\n";
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->close();
}
