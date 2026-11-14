// Click an object and drag its Gizmo. Compare --mode translate, rotate or both.
#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <iostream>
#include <map>

using namespace frameviz;

int main(int argc, char **argv) {
    std::string mode = "translate";
    float size = 0.8f;
    for (int i = 1; i < argc; i += 2) {
        std::string key = argv[i];
        if (i + 1 == argc || (key != "--mode" && key != "--size")) {
            std::cerr << "Usage: gizmo [--mode translate|rotate|both] [--size SIZE]\n";
            return 2;
        }
        if (key == "--mode") mode = argv[i + 1];
        else size = std::stof(argv[i + 1]);
    }
    // Three bits for translation, three for rotation, in XYZ order.
    const std::map<std::string, int> masks{{"translate", 0x07}, {"rotate", 0x38}, {"both", 0x3F}};
    if (!masks.count(mode)) {
        std::cerr << "Unknown Gizmo mode: " << mode << '\n';
        return 2;
    }
    const frameviz::example::Interrupt interrupt;
    auto viz = Viz::open();
    const auto box = viz->addBox({0.6f, 0.6f, 0.6f}, {-0.6f, 0, 0.3f},
                                 {0, 0, 0, 1}, {0.275f, 0.51f, 0.706f});
    const auto sphere = viz->addSphere(0.3f, {0.6f, 0, 0.3f}, {0, 0, 0, 1}, {1, 0.65f, 0});
    viz->setPickConfig({{"enabled", true}, {"mode", "object"}, {"button", 0}, {"ctrl_modifier", false}});
    viz->setCameraPose({2, -4, 2.5f}, {0, 0, 0.3f}, {0, 0, 1});
    viz->onEvent("picked", [&](const json &event) {
        auto handle = event.value("handle", "");
        if (handle == box || handle == sphere) viz->attachGizmo(handle, masks.at(mode), size, "world");
    });
    viz->onEvent("transformed", [](const json &event) {
        std::cout << "World pose: " << event.at("world_transform") << std::endl;
    });
    std::cout << "Click an object and drag its handles. Enter to exit." << std::endl;
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->close();
}
