// Clone, hide and delete objects using public handles.
#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <iostream>

int main() {
    const frameviz::example::Interrupt interrupt;
    auto viz = frameviz::Viz::open();
    auto box = viz->addBox({0.6f, 0.6f, 0.6f}, {-0.6f, 0, 0.3f}, {0, 0, 0, 1}, {1, 0.65f, 0});
    auto copy = viz->cloneObject(box);
    viz->setTransform(copy, {0.6f, 0, 0.3f}, {0, 0, 0, 1});
    viz->setColor(copy, {0, 0, 1});
    std::cout << "Two boxes. Enter to hide the original.\n";
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->setVisible(box, false);
    std::cout << "One visible box. Enter to delete the clone.\n";
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->removeObject(copy);
    std::cout << std::boolalpha << "Original exists: " << viz->isObjectAlive(box)
              << ", clone exists: " << viz->isObjectAlive(copy) << '\n';
    std::cout << "Enter to clear the scene.\n";
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->clear();
    std::cout << "Remaining objects: " << viz->getDisplayState().at("objects").size() << '\n';
    std::cout << "Enter to exit.\n";
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->close();
}
