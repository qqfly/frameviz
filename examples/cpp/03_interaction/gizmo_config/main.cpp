/**
 * FrameViz C++ Example - Gizmo Config
 *
 * 对应 Python: examples/python/03_interaction/use_gizmo_config.py
 */

#include <frameviz/viz.hpp>
#include <iostream>

using namespace frameviz;

int main() {
    std::cout << "==================================================" << std::endl;
    std::cout << "FrameViz Gizmo Config" << std::endl;
    std::cout << "==================================================" << std::endl;

    auto viz = Viz::open();
    std::cout << "[1] Connected" << std::endl;

    std::cout << "[2] Create box and attach gizmo..." << std::endl;
    auto box = viz->addBox({0.4f, 0.2f, 0.1f}, {0, 0, 0.05f}, {0, 0, 0, 1},
                           {1.0f, 0.6f, 0.2f});
    // mask=0x3F (default): all 6 DOFs enabled
    viz->attachGizmo(box, std::nullopt, 1.5f);
    std::cout << "    ✓ Gizmo attached (size=1.5, mask=0x3F)" << std::endl;

    std::cout << "[3] Switch to rotate only..." << std::endl;
    // mask=0x38 (0b111000): Rx|Ry|Rz only
    viz->setGizmoMode(0x38, 1.2f);
    std::cout << "    ✓ Switched to rotate only (mask=0x38, size=1.2)" << std::endl;

    std::cout << "\nDrag gizmo. Press Enter to exit..." << std::endl;
    std::cin.get();

    viz->detachGizmo();
    viz->close();
    return 0;
}
