/**
 * FrameViz C++ Example - Batch Transforms
 *
 * 对应 Python: examples/python/01_basic_primitives/use_batch_transforms_and_view_status.py
 */

#include <frameviz/viz.hpp>
#include <iostream>
#include <vector>

using namespace frameviz;

int main() {
    std::cout << "==================================================" << std::endl;
    std::cout << "FrameViz C++ - Batch Transforms" << std::endl;
    std::cout << "==================================================" << std::endl;

    std::cout << "\n[1] Connecting to FrameViz..." << std::endl;
    auto viz = Viz::open();
    std::cout << "    ✓ Connected" << std::endl;

    std::cout << "\n[2] Creating boxes..." << std::endl;
    std::vector<Handle> handles;
    for (int i = 0; i < 6; ++i) {
        float x = static_cast<float>(i) * 0.15f;
        Color color = {0.2f + static_cast<float>(i) * 0.1f, 0.6f, 0.9f};
        handles.push_back(viz->addBox({0.12f, 0.12f, 0.12f},
                                      {x, 0.0f, 0.06f},
                                      {0, 0, 0, 1}, color));
    }
    std::cout << "    ✓ Created " << handles.size() << " boxes" << std::endl;

    std::cout << "\n[3] Batch updating transforms..." << std::endl;
    std::vector<TransformItem> items;
    for (size_t i = 0; i < handles.size(); ++i) {
        Pose pose;
        pose.pos = {static_cast<float>(i) * 0.15f, 0.25f, 0.06f};
        pose.quat = {0, 0, 0, 1};
        items.push_back({handles[i], pose});
    }
    viz->setObjectTransforms(items);
    std::cout << "    ✓ Batch transform done" << std::endl;

    std::cout << "\nPress Enter to exit..." << std::endl;
    std::cin.get();

    viz->close();
    std::cout << "\n✓ Closed" << std::endl;

    return 0;
}
