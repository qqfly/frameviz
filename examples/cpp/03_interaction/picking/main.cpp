// Click a box or pass --points to read an original index and world hit.
#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <iostream>
#include <string_view>

using namespace frameviz;

int main(int argc, char **argv) {
    if (argc > 2 || (argc == 2 && std::string_view(argv[1]) != "--points")) {
        std::cerr << "Usage: picking [--points]\n";
        return 2;
    }
    const bool points = argc == 2;
    const frameviz::example::Interrupt interrupt;
    auto viz = Viz::open();
    const Color blue{0.275f, 0.51f, 0.706f};
    std::vector<Vec3> positions;
    std::vector<float> packed;
    Handle handle;
    if (points) {
        for (float x : {-0.6f, 0.0f, 0.6f}) {
            for (float y : {-0.6f, 0.0f, 0.6f}) {
                positions.push_back({x, y, 0.25f});
                packed.insert(packed.end(), {x, y, 0.25f});
            }
        }
        handle = viz->addPoints(packed, blue, 12);
    } else {
        handle = viz->addBox({1, 1, 1}, {0, 0, 0}, {0, 0, 0, 1}, blue);
    }
    viz->setPickConfig({{"enabled", true}, {"mode", points ? "point" : "object"},
                        {"button", 0}, {"ctrl_modifier", false}, {"point_threshold", 0.12}});
    viz->setCameraPose({2, -3, 2}, {0, 0, 0.2f}, {0, 0, 1});
    viz->onEvent("picked", [&, handle](const json &event) {
        if (event.value("handle", "") != handle) return;
        if (points && event.contains("point_index") && event["point_index"].is_number_unsigned()) {
            auto i = event["point_index"].get<std::size_t>();
            if (i < positions.size()) {
                std::cout << "Point " << i << ": input=" << json(positions[i])
                          << ", hit=" << event.at("point_world") << std::endl;
            }
        } else if (!points) {
            viz->setColor(handle, {1, 0.65f, 0});
            std::cout << "Picked " << handle << std::endl;
        }
    });
    std::cout << "Click the geometry. Enter to exit." << std::endl;
    if (!interrupt.waitForEnter(*viz)) return 130;
    viz->close();
}
