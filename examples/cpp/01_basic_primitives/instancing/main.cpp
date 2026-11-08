/**
 * FrameViz C++ Example - Instancing
 *
 * 展示高性能实例化渲染（10,000+ 对象）。
 *
 * 对应 Python: examples/python/01_basic_primitives/use_instancing.py
 */

#include <frameviz/viz.hpp>
#include <iostream>
#include <vector>
#include <random>

using namespace frameviz;

int main() {
    std::cout << "FrameViz C++ - Instancing Demo\n" << std::endl;

    auto viz = Viz::open();
    std::cout << "✓ Connected to FrameViz\n" << std::endl;

    viz->addPlane(50.0f, 50.0f, {0, 0, 0}, {0, 0, 0, 1},
                  {0.2f, 0.2f, 0.2f, 0.5f});
    viz->addAxes(2.0f);

    const int count = 10000;
    std::cout << "[1] Generating " << count << " instances..." << std::endl;

    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_real_distribution<float> pos_dist(-20.0f, 20.0f);
    std::uniform_real_distribution<float> height_dist(0.0f, 10.0f);

    std::vector<float> positions(count * 3);
    std::vector<float> quaternions(count * 4);
    std::vector<float> scales(count * 3);
    std::vector<Color> colors;
    colors.reserve(count);

    for (int i = 0; i < count; ++i) {
        positions[i * 3 + 0] = pos_dist(gen);
        positions[i * 3 + 1] = pos_dist(gen);
        positions[i * 3 + 2] = height_dist(gen);

        quaternions[i * 4 + 0] = 0.0f;
        quaternions[i * 4 + 1] = 0.0f;
        quaternions[i * 4 + 2] = 0.0f;
        quaternions[i * 4 + 3] = 1.0f;

        float scale = 0.1f;
        scales[i * 3 + 0] = scale;
        scales[i * 3 + 1] = scale;
        scales[i * 3 + 2] = scale;

        float h = positions[i * 3 + 2];
        const float r = h / 10.0f;
        const float g = 128.0f / 255.0f;
        const float b = 1.0f - h / 10.0f;
        colors.push_back({r, g, b});
    }

    std::cout << "    ✓ Data generated" << std::endl;

    std::cout << "[2] Creating box instances..." << std::endl;
    auto handle = viz->addInstances(InstanceType::BOX, positions, quaternions, scales, colors);
    std::cout << "    ✓ " << count << " instances created\n" << std::endl;

    viz->setCameraPose({30, 30, 20}, {0, 0, 5}, {0, 0, 1});

    std::cout << std::string(60, '=') << std::endl;
    std::cout << "✓ Rendering " << count << " instances!" << std::endl;
    std::cout << "\nPress Enter to exit..." << std::endl;
    std::cout << std::string(60, '=') << std::endl;

    std::cin.get();
    viz->close();
    return 0;
}
