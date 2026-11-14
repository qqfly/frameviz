/**
 * FrameViz C++ Example - Camera Controls + fit_object
 *
 * 对应 Python: examples/python/02_camera_views/use_camera_controls_fit_object.py
 */

#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <iostream>

using namespace frameviz;

int main() {
    std::cout << "==================================================" << std::endl;
    std::cout << "FrameViz Camera Controls + fit_object" << std::endl;
    std::cout << "==================================================" << std::endl;

    const frameviz::example::Interrupt interrupt;
    auto viz = Viz::open();
    auto waitStep = [&](const std::string &prompt) {
        std::cout << prompt << '\n';
        return interrupt.waitForEnter(*viz);
    };

    auto red_box = viz->addBox({1, 1, 1}, {-2, 0, 0.5f}, {0, 0, 0, 1}, {1, 0, 0});
    auto green_box = viz->addBox({1, 1, 1}, {2, 0, 0.5f}, {0, 0, 0, 1}, {0, 1, 0});
    (void)green_box;
    viz->addAxes(1.5f, 0.03f);

    viz->addText2D("Camera controls demo", 12, 12, 14, {1, 1, 1});

    viz->resetCamera();
    if (!waitStep("Step 1: Scene created. Press Enter...")) return 130;

    viz->resetCamera("fit_object", red_box);
    if (!waitStep("Step 2: Should focus on red box. Press Enter...")) return 130;

    json controls = {
        {"zoom_to_cursor", true},
        {"zoom_sensitivity", 1.2},
        {"orbit_enabled", true},
        {"pan_enabled", true},
        {"zoom_enabled", true}
    };
    viz->setCameraControls(controls);
    if (!waitStep("Step 3: zoom_to_cursor enabled. Press Enter...")) return 130;

    viz->setCameraControls({{"zoom_to_cursor", false}});
    if (!waitStep("Step 4: zoom_to_cursor disabled. Press Enter...")) return 130;

    viz->setCameraControls({{"zoom_enabled", false}});
    if (!waitStep("Step 5: zoom disabled. Press Enter...")) return 130;
    viz->setCameraControls({{"zoom_enabled", true}});
    auto camera = viz->getCameraView();
    camera["projection"]["fov"] = 40; // Vertical field of view, in degrees.
    viz->setCameraView(camera);
    viz->setViewConfig({{"show_axes", false}, {"show_grid", false}});
    std::cout << viz->getCameraView() << '\n';
    if (!waitStep("Press Enter to exit.")) return 130;

    viz->close();
    return 0;
}
