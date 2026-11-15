// Load an STL/DAE URL and compare world and screen labels.
#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <iostream>

using namespace frameviz;

int main(int argc, char **argv) {
    if (argc != 2) {
        std::cerr << "Usage: load_mesh_and_labels HTTP_MODEL_URL (see examples/README.md for the built-in sample)\n";
        return 2;
    }
    const frameviz::example::Interrupt interrupt;
    auto viz = Viz::open("ws://127.0.0.1:9527", "Model and labels");
    viz->setViewConfig({{"background", {1, 1, 1}}, {"show_axes", false}});
    SceneNodeOptions modelOptions;
    modelOptions.name = "Loaded mesh";
    const auto model = viz->loadMesh(argv[1], {0, 0, 0}, {0, 0, 0, 1}, {1, 1, 1},
                                     Color{0.19f, 0.52f, 0.75f}, modelOptions);
    // The child label moves with the mesh. The overlay uses screen pixels.
    SceneNodeOptions label;
    label.parent = model;
    viz->addText3D("3D label - moves with model", {0, 0, 1}, 14, {0, 0, 0}, "rgba(255,255,255,0.9)", label);
    viz->addText2D("Screen label - stays here", 24, 65, 14, {0, 0, 0});
    viz->setCameraPose({2.3f, -3.5f, 2.2f}, {0.25f, 0, 0.45f}, {0, 0, 1});
    auto ready = viz->waitForEvent("object_ready", [&](const json &event) {
        return event.value("handle", "") == model;
    }, std::chrono::seconds(10));
    if (!ready) {
        auto failure = viz->waitForEvent("object_failed", [&](const json &event) {
            return event.value("handle", "") == model;
        }, std::chrono::seconds(0));
        std::cerr << "Model failed to load: "
                  << (failure ? failure->value("message", "check the model URL")
                              : "the Viewer did not report readiness") << '\n';
        viz->close();
        return 1;
    }
    std::cout << "The blue model is ready. Press Enter to move it and its 3D label.\n";
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->setTransform(model, {0.9f, 0, 0}, {0, 0, 0, 1});
    std::cout << "The screen label stays fixed. Enter to exit.\n";
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->close();
}
