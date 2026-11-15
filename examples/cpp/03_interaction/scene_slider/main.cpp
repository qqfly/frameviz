// Drag or type a number. Use --mode commit to update on release.
#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <iostream>
#include <string_view>

using namespace frameviz;

int main(int argc, char **argv) {
    const std::string mode = argc == 3 ? argv[2] : "continuous";
    if (argc != 1 && (argc != 3 || std::string_view(argv[1]) != "--mode" ||
                      (mode != "continuous" && mode != "commit"))) {
        std::cerr << "Usage: scene_slider [--mode continuous|commit]\n";
        return 2;
    }
    const frameviz::example::Interrupt interrupt;
    auto viz = Viz::open();
    const auto box = viz->addBox({1, 1, 1}, {0, 0, 0}, {0, 0, 0, 1}, {0.392f, 0.584f, 0.929f});
    const auto slider = viz->addWidget("number", "Box X", 0,
        {{"minimum", -2}, {"maximum", 2}, {"step", 0.01}, {"update_mode", mode}});
    const auto reset = viz->addWidget("button", "Reset");
    viz->onWidgetChange(slider, [&](const json &event) {
        viz->setTransform(box, {event.at("value").get<float>(), 0, 0}, {0, 0, 0, 1});
    });
    viz->onWidgetChange(reset, [&](const json &) {
        viz->setWidgetValue(slider, 0);
        viz->setTransform(box, {0, 0, 0}, {0, 0, 0, 1});
    });
    std::cout << "Drag or type a number, then try Reset. Enter to exit." << std::endl;
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->close();
}
