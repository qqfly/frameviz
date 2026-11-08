/**
 * FrameViz C++ Example - Camera Controls + fit_object
 *
 * 对应 Python: examples/python/02_camera_views/use_camera_controls_fit_object.py
 */

#include <frameviz/viz.hpp>
#include <iostream>

using namespace frameviz;

static void waitStep(const std::string &prompt) {
    std::cout << prompt << std::endl;
    std::cin.get();
}

int main() {
    std::cout << "==================================================" << std::endl;
    std::cout << "FrameViz Camera Controls + fit_object" << std::endl;
    std::cout << "==================================================" << std::endl;

    auto viz = Viz::open();

    auto red_box = viz->addBox({1, 1, 1}, {-2, 0, 0.5f}, {0, 0, 0, 1}, {1, 0, 0});
    auto green_box = viz->addBox({1, 1, 1}, {2, 0, 0.5f}, {0, 0, 0, 1}, {0, 1, 0});
    (void)green_box;
    viz->addAxes(1.5f, 0.03f);

    viz->addText2D("Camera controls demo", 12, 12, 14, {1, 1, 1});

    viz->resetCamera();
    waitStep("Step 1: Scene created. Press Enter...");

    viz->resetCamera("fit_object", red_box);
    waitStep("Step 2: Should focus on red box. Press Enter...");

    json controls = {
        {"zoom_to_cursor", true},
        {"zoom_sensitivity", 1.2},
        {"orbit_enabled", true},
        {"pan_enabled", true},
        {"zoom_enabled", true}
    };
    viz->setCameraControls(controls);
    waitStep("Step 3: zoom_to_cursor enabled. Press Enter...");

    viz->setCameraControls({{"zoom_to_cursor", false}});
    waitStep("Step 4: zoom_to_cursor disabled. Press Enter...");

    viz->setCameraControls({{"zoom_enabled", false}});
    waitStep("Step 5: zoom disabled. Press Enter...");
    viz->setCameraControls({{"zoom_enabled", true}});

    viz->close();
    return 0;
}
