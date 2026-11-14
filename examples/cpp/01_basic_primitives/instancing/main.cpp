// Draw and update a group of colored boxes with one handle.
#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <iostream>

using namespace frameviz;

int main() {
    const frameviz::example::Interrupt interrupt;
    auto viz = Viz::open();
    // The grid cell size is 0.4 world units. Each position is xyz.
    const std::vector<float> positions = {0, 0, 0.15f, 0.4f, 0, 0.15f, 0.8f, 0, 0.15f};
    const std::vector<Color> colors = {{0.2f, 0.5f, 0.8f}, {0.3f, 0.7f, 0.3f}, {0.9f, 0.5f, 0.2f}};
    auto handle = viz->addInstances(InstanceType::BOX, positions, {}, {}, colors,
                                    std::nullopt, std::nullopt, Vec3{0.3f, 0.3f, 0.3f});
    viz->setCameraPose({2, -3, 2}, {0.4f, 0.2f, 0.2f}, {0, 0, 1});
    std::cout << "Three boxes share one handle. Enter to update and add a fourth.\n";
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->updateInstances(handle, {0, 0.4f, 0.45f, 0.4f, 0.4f, 0.45f, 0.8f, 0.4f, 0.45f, 0.4f, 0.8f, 0.15f},
                         {}, {}, {colors[2], colors[1], colors[0], {0.6f, 0.3f, 0.7f}});
    std::cout << "Press Enter to exit.\n";
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->close();
}
