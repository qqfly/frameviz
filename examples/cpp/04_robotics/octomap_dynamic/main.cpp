/**
 * FrameViz C++ Example - Octomap Dynamic Update
 *
 * 对应 Python: examples/python/04_robotics/use_octomap_dynamic.py
 */

#include <frameviz/viz.hpp>
#include <iostream>
#include <vector>
#include <random>
#include <thread>
#include <chrono>

using namespace frameviz;

static void buildOctomap(int grid, float cell, float fill_prob,
                         std::vector<float> &positions,
                         std::vector<Color> &colors, std::mt19937 &gen)
{
    std::uniform_real_distribution<float> prob(0.0f, 1.0f);
    positions.clear();
    colors.clear();

    for (int x = 0; x < grid; ++x) {
        for (int y = 0; y < grid; ++y) {
            for (int z = 0; z < grid; ++z) {
                if (prob(gen) < fill_prob) {
                    float px = (x - grid / 2) * cell;
                    float py = (y - grid / 2) * cell;
                    float pz = z * cell;
                    positions.push_back(px);
                    positions.push_back(py);
                    positions.push_back(pz);

                    float r = static_cast<float>(80 + z * 6) / 255.0f;
                    float g = static_cast<float>(60 + x * 5) / 255.0f;
                    float b = static_cast<float>(140 + y * 4) / 255.0f;
                    colors.push_back({r, g, b});
                }
            }
        }
    }
}

int main()
{
    std::cout << "=================================================="
              << std::endl;
    std::cout << "FrameViz Octomap Dynamic Update" << std::endl;
    std::cout << "=================================================="
              << std::endl;

    auto viz = Viz::open();

    const int grid = 16;
    const float cell = 0.2f;
    std::mt19937 gen(2);

    std::vector<float> positions;
    std::vector<Color> colors;

    buildOctomap(grid, cell, 0.15f, positions, colors, gen);
    auto handle =
        viz->addInstances(InstanceType::BOX, positions, {}, {}, colors,
                          std::nullopt, 0.6f, Vec3{cell, cell, cell});

    viz->addText2D("Octomap dynamic update (updates every 2s)", 12, 12, 14,
                   {1, 1, 1});
    viz->setCameraPose({5, 5, 5}, {0, 0, 1}, {0, 0, 1});

    for (int step = 0; step < 500; ++step) {
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
        buildOctomap(grid, cell, 0.15f, positions, colors, gen);
        viz->updateInstances(handle, positions, {}, {}, colors);
        std::cout << "Update " << (step + 1)
                  << ": instances=" << positions.size() / 3 << std::endl;
    }

    std::cout << "Press Enter to exit..." << std::endl;
    std::cin.get();

    viz->close();
    return 0;
}
