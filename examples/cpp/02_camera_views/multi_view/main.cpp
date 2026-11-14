// Open two Views. Use --app for desktop windows and --independent for separate scenes.
#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <iostream>
#include <string_view>

using namespace frameviz;

int main(int argc, char **argv) {
    bool independent = false;
    bool app = false;
    for (int i = 1; i < argc; ++i) {
        const std::string_view argument = argv[i];
        if (argument == "--independent") {
            independent = true;
        } else if (argument == "--app") {
            app = true;
        } else {
            std::cerr << "Usage: multi_view [--app] [--independent]\n";
            return 2;
        }
    }
    const int windowMode = app ? 2 : 1;
    const std::string host = "ws://127.0.0.1:9527";
    const frameviz::example::Interrupt interrupt;
    auto left = Viz::open(host, "Front View", 800, 600, true, std::nullopt, windowMode);
    auto right = Viz::open(host, "Top View", 800, 600, true,
                           independent ? std::nullopt : std::optional<std::string>(left->sceneId()), windowMode);
    auto box = left->addBox({0.8f, 0.6f, 0.6f}, {0, 0, 0.3f}, {0, 0, 0, 1}, {0.275f, 0.51f, 0.706f});
    if (independent) right->addSphere(0.3f, {0, 0, 0.3f}, {0, 0, 0, 1}, {1, 0.65f, 0});
    left->setCameraPose({3, -4, 2}, {0, 0, 0.3f}, {0, 0, 1});
    right->setCameraPose({0, 0, 4}, {0, 0, 0.3f}, {0, 1, 0});
    for (auto *view : {left.get(), right.get()}) {
        std::cout << "scene_id=" << view->sceneId() << " view_id=" << view->viewId() << '\n';
    }
    std::cout << (app ? "Rotate one window and compare the other. Enter to move the box.\n"
                      : "Rotate one View or refresh a tab. Enter to move the box.\n");
    if (!interrupt.waitForEnter(*right, *left)) return 130;
    left->setTransform(box, {0.7f, 0, 0.3f}, {0, 0, 0, 1});
    std::cout << "Check which Views show the move. Enter to exit.\n";
    if (!interrupt.waitForEnter(*right, *left)) return 130;
    right->close();
    left->close();
}
