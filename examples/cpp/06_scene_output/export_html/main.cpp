// Export an interactive lesson with a closed, application-computed path.
#include <frameviz/viz.hpp>
#include <filesystem>
#include <iostream>

using frameviz::json;

int main() {
    auto viz = frameviz::Viz::open("ws://127.0.0.1:9527", "Lesson", 800, 600, true, std::nullopt, 0);
    auto box = viz->addBox({0.6f, 0.6f, 0.6f}, {0, 0, 0.3f}, {0, 0, 0, 1}, {0.192f, 0.522f, 0.745f});
    viz->addPlane(4, 3, {0, 0, 0}, {0, 0, 0, 1}, {0.886f, 0.910f, 0.941f});
    viz->setCameraPose({3, -4, 3}, {0.5f, 0, 0.3f}, {0, 0, 1});
    viz->setViewConfig({{"show_axes", false}, {"show_grid", false}});
    // Times are seconds. Poses contain xyz translation and xyzw rotation.
    const json tracks = {{box, json::array({
        {{"time", 0}, {"pose", {0, 0, 0.3, 0, 0, 0, 1}}},
        {{"time", 1}, {"pose", {1.2, 0, 0.3, 0, 0, 0, 1}}},
        {{"time", 2}, {"pose", {1.2, 0.8, 0.3, 0, 0, 0, 1}}},
        {{"time", 3}, {"pose", {0, 0.8, 0.3, 0, 0, 0, 1}}},
        {{"time", 4}, {"pose", {0, 0, 0.3, 0, 0, 0, 1}}},
    })}};
    const auto output = std::filesystem::absolute("lesson.html");
    viz->exportHtml(output.string(), tracks);
    std::cout << "Open " << output << " in a browser and press Play.\n";
    viz->close();
}
