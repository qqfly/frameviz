// Edit staged values and click Apply to change the box.
#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <iostream>

using namespace frameviz;

int main() {
    const frameviz::example::Interrupt interrupt;
    auto viz = Viz::open();
    const Color blue{0.275f, 0.51f, 0.706f};
    const auto box = viz->addBox({1, 1, 1}, {0, 0, 0}, {0, 0, 0, 1}, blue);
    const auto panel = viz->addWidget("group", "Box settings");
    const json parent = {{"parent", panel}};
    const auto x = viz->addWidget("number", "X", 0, {{"parent", panel},
        {"minimum", -2}, {"maximum", 2}, {"step", 0.01}, {"update_mode", "commit"}});
    const auto shown = viz->addWidget("checkbox", "Visible", true, parent);
    const auto color = viz->addWidget("select", "Color", "Blue",
        {{"parent", panel}, {"choices", {"Blue", "Orange"}}});
    const auto name = viz->addWidget("text_input", "Name", "Box", parent);
    viz->addWidget("text", "Instructions", "Edit settings, then press Apply.", parent);
    viz->onWidgetChange(x, [](const json &event) {
        std::cout << "X submitted: " << event.at("value") << ' ' << event.at("source") << std::endl;
    });
    viz->onWidgetChange(viz->addWidget("button", "Apply", nullptr, parent), [&](const json &) {
        viz->setTransform(box, {viz->getWidgetValue(x).get<float>(), 0, 0}, {0, 0, 0, 1});
        viz->setVisible(box, viz->getWidgetValue(shown).get<bool>());
        viz->setColor(box, viz->getWidgetValue(color) == "Blue" ? blue : Color{1, 0.65f, 0});
        viz->setObjectMetadata(box, viz->getWidgetValue(name).get<std::string>(), json::object());
    });
    viz->onWidgetChange(viz->addWidget("button", "Set X from code", nullptr, parent), [&](const json &) {
        // The first write updates the control only. The second also calls the handler.
        viz->setWidgetValue(x, 0);
        viz->setWidgetValue(x, 1, true);
    });
    std::cout << "Edit the controls, click Apply, then try Set X from code. Enter to exit." << std::endl;
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->close();
}
