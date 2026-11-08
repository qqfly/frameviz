/**
 * FrameViz C++ Example - Lines with Indices
 *
 * 对应 Python: examples/python/01_basic_primitives/use_lines_indices.py
 */

#include <frameviz/viz.hpp>
#include <iostream>
#include <vector>

using namespace frameviz;

std::vector<float> offsetPoints(const std::vector<float> &points, float offset_x) {
    std::vector<float> out = points;
    for (size_t i = 0; i < out.size(); i += 3) {
        out[i] += offset_x;
    }
    return out;
}

int main() {
    std::cout << "==================================================" << std::endl;
    std::cout << "FrameViz add_lines.indices Test" << std::endl;
    std::cout << "==================================================" << std::endl;

    auto viz = Viz::open();

    std::vector<float> base = {
        -1.0f, 0.0f, 0.5f,
         1.0f, 0.0f, 0.5f,
         1.0f, 1.0f, 0.5f,
        -1.0f, 1.0f, 0.5f,
    };
    std::vector<uint32_t> indices = {0, 1, 2, 3};

    auto left_points = offsetPoints(base, -3.0f);
    auto right_points = offsetPoints(base, 3.0f);

    auto handle_left = viz->addLines(left_points, indices, 2.0f,
                                     {0.0f, 1.0f, 0.0f});
    auto handle_right = viz->addLines(right_points, {}, 2.0f,
                                      {1.0f, 0.0f, 0.0f});

    viz->addText2D("Left: indices (2 segments)  Right: no indices (polyline)", 12, 12, 14, {1, 1, 1});

    std::cout << "Left handle=" << handle_left << ", Right handle=" << handle_right << std::endl;
    std::cout << "Observe: left has 2 segments, right is a continuous polyline." << std::endl;

    std::cout << "\nPress Enter to exit..." << std::endl;
    std::cin.get();

    viz->close();
    return 0;
}
