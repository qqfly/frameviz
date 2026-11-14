/**
 * FrameViz C++ Example - Point Cloud and Mesh
 *
 * 对应 Python: examples/python/01_basic_primitives/use_pointcloud_mesh.py
 */

#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <iostream>
#include <vector>
#include <cmath>

using namespace frameviz;

int main() {
    std::cout << "==================================================" << std::endl;
    std::cout << "FrameViz Point Cloud + Mesh" << std::endl;
    std::cout << "==================================================" << std::endl;

    const frameviz::example::Interrupt interrupt;
    auto viz = Viz::open();

    // Point cloud: circle
    const int point_count = 2000;
    std::vector<float> positions(point_count * 3);
    std::vector<Color> colors;
    colors.reserve(point_count);

    for (int i = 0; i < point_count; ++i) {
        float t = static_cast<float>(i) / point_count * 2.0f * 3.1415926f;
        float r = 2.0f;
        positions[i * 3 + 0] = r * std::cos(t);
        positions[i * 3 + 1] = r * std::sin(t);
        positions[i * 3 + 2] = 0.2f * std::sin(3.0f * t);

        const float cr = 0.5f + 0.5f * std::cos(t);
        const float cg = 0.5f + 0.5f * std::sin(t);
        const float cb = 200.0f / 255.0f;
        colors.push_back({cr, cg, cb});
    }

    viz->addPoints(positions, colors, 2.0f);

    // Simple pyramid mesh
    std::vector<float> vertices = {
        0.0f, 0.0f, 1.0f,  // top
        -0.5f, -0.5f, 0.0f,
        0.5f, -0.5f, 0.0f,
        0.5f, 0.5f, 0.0f,
        -0.5f, 0.5f, 0.0f,
    };
    std::vector<uint32_t> faces = {
        0, 1, 2,
        0, 2, 3,
        0, 3, 4,
        0, 4, 1,
        1, 2, 3,
        1, 3, 4,
    };

    SceneNodeOptions left, right;
    left.pose = RigidPose{{-0.65f, 0, 0}};
    right.pose = RigidPose{{0.65f, 0, 0}};
    viz->addMesh(vertices, faces, FacesFormat::TRI, {1, 1, 1}, {}, std::nullopt, false, true, left);
    // In polygon format, prefix each face with its vertex count.
    viz->addMesh(vertices, {4, 1, 2, 3, 4}, FacesFormat::POLY,
                 {1, 0.65f, 0}, {}, std::nullopt, false, true, right);

    viz->setCameraPose({5, 5, 3}, {0, 0, 0.3f}, {0, 0, 1});

    std::cout << "\nPress Enter to exit..." << std::endl;
    if (!interrupt.waitForEnter(*viz)) return 130;

    viz->close();
    return 0;
}
