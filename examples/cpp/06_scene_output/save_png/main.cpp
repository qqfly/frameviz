// Save a PNG without an interactive Viewer. See examples/README.md for setup.
#include <frameviz/viz.hpp>
#include <filesystem>
#include <iostream>

int main() {
    auto viz = frameviz::Viz::open("ws://127.0.0.1:9527", "PNG", 800, 600, true, std::nullopt, 0);
    viz->addBox({1.4f, 0.7f, 0.5f}, {0, 0, 0}, {0, 0, 0, 1}, {0.192f, 0.522f, 0.745f});
    viz->setViewConfig({{"show_axes", false}, {"show_grid", false}, {"background", {1, 1, 1}}});
    const frameviz::json camera = {
        {"eye", {3, -4, 3}}, {"target", {0, 0, 0}}, {"up", {0, 0, 1}},
        {"projection", {{"type", "perspective"}, {"fov", 35}}},
    };
    viz->screenshot("scene.png", camera, 640, 480);
    std::cout << "Open " << std::filesystem::absolute("scene.png")
              << " to see the 640x480 screenshot.\n";
    viz->close();
}
