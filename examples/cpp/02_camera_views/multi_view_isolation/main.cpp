/**
 * FrameViz C++ Example - Multi-View Isolation
 *
 * 展示多视图隔离特性，现在支持场景共享。
 *
 * 对应 Python: examples/python/02_camera_views/use_multi_view_isolation.py
 */

#include <frameviz/viz.hpp>
#include <iostream>
#include <thread>
#include <chrono>

using namespace frameviz;

int main() {
    std::cout << "==================================================" << std::endl;
    std::cout << "FrameViz Multi-View Isolation (with Scene Sharing)" << std::endl;
    std::cout << "==================================================" << std::endl;

    std::cout << "\n[1] Creating View A..." << std::endl;
    auto viz_a = Viz::open("ws://127.0.0.1:9527", "View A", 800, 600, true);
    std::cout << "    ✓ View A created: view=" << viz_a->viewId()
              << ", scene=" << viz_a->sceneId() << "\n" << std::endl;

    std::this_thread::sleep_for(std::chrono::milliseconds(300));

    std::cout << "[2] Creating View B sharing View A's scene..." << std::endl;
    auto viz_b = Viz::open("ws://127.0.0.1:9527", "View B", 800, 600, true,
                           std::optional<std::string>(viz_a->sceneId()));  // 共享场景！
    std::cout << "    ✓ View B created: view=" << viz_b->viewId()
              << ", scene=" << viz_b->sceneId() << " (shared)\n" << std::endl;

    std::cout << "[3] Adding shared scene objects..." << std::endl;
    viz_a->addBox({1, 1, 1}, {0, 0, 0.5f}, {0, 0, 0, 1}, {1, 0, 0});  // red box
    viz_a->addText2D("View A", 12, 12, 14, {1, 1, 1});
    viz_a->setCameraPose({4, 4, 3}, {0, 0, 0.5f}, {0, 0, 1});

    viz_b->addText2D("View B", 12, 12, 14, {1, 1, 1});
    viz_b->setCameraPose({4, -4, 3}, {0, 0, 0.5f}, {0, 0, 1});
    std::cout << "    ✓ Objects added (visible in both views)\n" << std::endl;

    std::cout << "\n" << std::string(60, '=') << std::endl;
    std::cout << "✓ Multi-view isolation test complete!" << std::endl;
    std::cout << "\nKey observations:" << std::endl;
    std::cout << "  • View A and View B share the same scene" << std::endl;
    std::cout << "  • Both views can see the red box" << std::endl;
    std::cout << "  • Each view has independent camera position" << std::endl;
    std::cout << "  • Each view has its own overlay text" << std::endl;
    std::cout << "\nPress Enter to exit..." << std::endl;
    std::cout << std::string(60, '=') << std::endl;

    std::cin.get();

    // Cleanup
    std::cout << "\n[4] Cleaning up..." << std::endl;
    viz_a->close();
    viz_b->close();
    std::cout << "    ✓ All views closed" << std::endl;
    std::cout << "\nDone." << std::endl;

    return 0;
}
