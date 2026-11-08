/**
 * FrameViz C++ Example - Snapshot Large Buffer
 *
 * 对应 Python: examples/python/01_basic_primitives/use_snapshot_large_buffer.py
 */

#include <frameviz/viz.hpp>
#include <iostream>
#include <vector>
#include <random>

using namespace frameviz;

int main() {
    std::cout << "==================================================" << std::endl;
    std::cout << "FrameViz Snapshot Large Buffer Test" << std::endl;
    std::cout << "==================================================" << std::endl;

    auto viz = Viz::open();

    const int point_count = 300000;
    std::vector<float> positions(point_count * 3);
    std::vector<Color> colors;
    colors.reserve(point_count);

    std::mt19937 gen(0);
    std::normal_distribution<float> dist(0.0f, 1.0f);
    std::uniform_int_distribution<int> color_dist(0, 255);

    for (int i = 0; i < point_count; ++i) {
        positions[i * 3 + 0] = dist(gen);
        positions[i * 3 + 1] = dist(gen);
        positions[i * 3 + 2] = 0.2f * dist(gen);

        const float r = static_cast<float>(color_dist(gen)) / 255.0f;
        const float g = static_cast<float>(color_dist(gen)) / 255.0f;
        const float b = static_cast<float>(color_dist(gen)) / 255.0f;
        colors.push_back({r, g, b});
    }

    auto handle = viz->addPoints(positions, colors, 2.0f);
    viz->addText2D("Large buffer snapshot test: refresh viewer", 12, 12, 14, {1, 1, 1});

    std::cout << "Added point cloud handle=" << handle << ", count=" << point_count << std::endl;
    std::cout << "Refresh viewer to verify snapshot restore." << std::endl;

    std::cout << "\nPress Enter to exit..." << std::endl;
    std::cin.get();

    viz->close();
    return 0;
}
