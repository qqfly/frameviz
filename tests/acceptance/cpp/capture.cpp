#include <frameviz/viz.hpp>
#include <iostream>
#include <stdexcept>

int main(int argc, char **argv) {
    if (argc != 4) return 2;
    auto viz = frameviz::Viz::connect(argv[1], argv[2]);
    const auto before = viz->getCameraView();
    auto temporary = before;
    temporary["eye"] = {-4, 2, 2};
    auto bytes = viz->screenshot("alternate.png", temporary, 320, 240);
    auto normal = viz->screenshot("normal.png", std::nullopt, 320, 240);
    if (bytes.empty() || normal == bytes || viz->getCameraView() != before) return 3;
    if (viz->screenshot("", temporary, 320, 240).empty()) return 4;
    try {
        viz->screenshot("invalid.png", std::nullopt, 0, 240);
        return 5;
    } catch (const std::runtime_error &error) {
        if (std::string(error.what()).find("8192") == std::string::npos) throw;
    }
    viz->exportHtml("lesson.html", {
        {argv[3], frameviz::json::array({
            {{"time", 0}, {"pose", {0, 0, 0, 0, 0, 0, 1}}},
            {{"time", 1}, {"pose", {1, 0, 0, 0, 0, 0, 1}}}
        })}
    });
    viz->close();
}
