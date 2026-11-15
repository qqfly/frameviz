// Redraw an application-computed path when the goal's world pose changes.
#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <cmath>
#include <iostream>

using namespace frameviz;

int main() {
    const frameviz::example::Interrupt interrupt;
    auto viz = Viz::open();
    SceneNodeOptions goalOptions;
    goalOptions.name = "Goal";
    const auto goal = viz->addAxes(0.45f, 0.02f, {1, 1, 0.5f}, {0, 0, 0, 1}, goalOptions);
    viz->setViewConfig({{"show_axes", false}, {"show_grid", true}});
    viz->setCameraPose({4, -5, 3}, {0, 0, 0.5f}, {0, 0, 1});
    viz->attachGizmo(goal, 0x07, 0.6f);
    Handle path;
    auto redraw = [&](const Vec3 &position) {
        // Overlap small spheres to give the path real thickness in the scene.
        std::vector<float> vertices;
        for (int i = 0; i < 96; ++i) {
            const auto t = i / 95.0f;
            vertices.insert(vertices.end(), {t * position[0], t * position[1],
                t * position[2] + 0.3f * std::sin(3.14159265f * t)});
        }
        if (path.empty()) {
            path = viz->addInstances(InstanceType::SPHERE, vertices, {}, {}, {},
                                     Color{0.06f, 0.46f, 0.43f}, std::nullopt, Vec3{0.04f, 0, 0});
        } else {
            viz->updateInstances(path, vertices);
        }
    };
    redraw({1, 1, 0.5f});
    viz->onEvent("transformed", [&](const json &event) {
        if (event.value("handle", "") == goal) {
            redraw(event.at("world_transform").at("position").get<Vec3>());
        }
    });
    std::cout << "Drag the goal. Enter to exit." << std::endl;
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->close();
}
