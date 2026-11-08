/**
 * FrameViz C++ Example - Multi-View
 *
 * 展示多视图与场景管理，包括场景共享。
 * 现在支持 shareScene 参数，可以创建多个视图共享同一个场景。
 *
 * 对应 Python: examples/python/02_camera_views/use_multi_view_demo.py
 */

#include <frameviz/viz.hpp>
#include <iostream>
#include <thread>
#include <chrono>
#include <random>

using namespace frameviz;

int main() {
    std::cout << "======================================================" << std::endl;
    std::cout << "FrameViz C++ - Multi-View Demo (with Scene Sharing)" << std::endl;
    std::cout << "======================================================" << std::endl;

    std::cout << "\n[1] Creating main view (Tauri) with new scene..." << std::endl;
    auto viz1 = Viz::open("ws://127.0.0.1:9527", "Main View", 800, 600, true);
    std::cout << "    ✓ viz1 (Main View) created: view=" << viz1->viewId()
              << ", scene=" << viz1->sceneId() << "\n" << std::endl;

    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    std::cout << "[2] Creating browser view sharing main scene..." << std::endl;
    auto viz2 = Viz::open("ws://127.0.0.1:9527", "Browser View", 800, 600, true,
                           std::optional<std::string>(viz1->sceneId()), 1);  // 共享场景 + 浏览器窗口
    std::cout << "    ✓ viz2 (Browser View) created: view=" << viz2->viewId()
              << ", scene=" << viz2->sceneId() << " (shared, browser)\n" << std::endl;

    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    std::cout << "[3] Creating independent scene view..." << std::endl;
    auto viz3 = Viz::open("ws://127.0.0.1:9527", "Independent Scene", 800, 600, true);
    std::cout << "    ✓ viz3 (Independent Scene) created: view=" << viz3->viewId()
              << ", scene=" << viz3->sceneId() << " (independent)\n" << std::endl;

    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    std::cout << "[4] Creating frameless view sharing main scene..." << std::endl;
    auto viz4 = Viz::open("ws://127.0.0.1:9527", "Frameless View", 800, 600, false,
                           std::optional<std::string>(viz1->sceneId()));  // 共享场景
    std::cout << "    ✓ viz4 (Frameless View) created: view=" << viz4->viewId()
              << ", scene=" << viz4->sceneId() << " (shared, no title bar)\n" << std::endl;

    std::cout << "[5] Creating scene objects for shared scene (viz1, viz2, viz4)..." << std::endl;
    viz1->addAxes(1.0f);
    viz1->addBox({1, 1, 1}, {0, 0, 0.5f}, {0, 0, 0, 1}, {1, 0, 0});         // red
    viz1->addSphere(0.3f, {1.5, 0, 0.3f}, {0, 0, 0, 1}, {0, 1, 0});          // green
    std::cout << "    ✓ Shared scene objects: axes, box(red), sphere(green)\n" << std::endl;

    std::cout << "[6] Creating scene objects for independent scene (viz3)..." << std::endl;
    viz3->addAxes(2.0f);
    viz3->addCylinder(0.5f, 2.0f, {0, 0, 1}, {0, 0, 0, 1}, {0, 0, 1});     // blue
    viz3->addCone(0.4f, 1.0f, {2, 0, 0.5f}, {0, 0, 0, 1}, {1, 1, 0});        // yellow

    // 添加点云 (品红色)
    const int n = 1000;
    std::vector<float> points(n * 3);
    std::vector<Color> colors;
    colors.reserve(n);

    std::mt19937 gen(42);
    std::normal_distribution<float> dist(0.0f, 0.5f);
    for (int i = 0; i < n; ++i) {
        points[i * 3 + 0] = dist(gen);
        points[i * 3 + 1] = dist(gen);
        points[i * 3 + 2] = dist(gen) + 2.5f;
        colors.push_back({1.0f, 0.0f, 1.0f});  // magenta
    }
    viz3->addPoints(points, colors, 3.0f);
    std::cout << "    ✓ Independent scene: axes, cylinder(blue), cone(yellow), points(magenta)\n" << std::endl;

    std::cout << "[7] Setting camera poses..." << std::endl;
    viz1->setCameraPose({5, 5, 3}, {0, 0, 0.5f}, {0, 0, 1});
    viz2->setCameraPose({-5, 5, 3}, {0, 0, 0.5f}, {0, 0, 1});  // 侧视图
    viz4->setCameraPose({0, 0, 5}, {0, 0, 0.5f}, {0, 0, 1});   // 俯视图
    std::cout << "    ✓ Camera poses set\n" << std::endl;

    std::cout << "\n" << std::string(70, '=') << std::endl;
    std::cout << "✓ Multi-view setup complete!" << std::endl;
    std::cout << "\nCurrent state:" << std::endl;
    std::cout << "  • viz1 (Main View)    - Standard window, owns the scene" << std::endl;
    std::cout << "  • viz2 (Browser View) - Browser window, shares viz1's scene" << std::endl;
    std::cout << "  • viz3 (Independent)  - Standard window, independent scene with point cloud" << std::endl;
    std::cout << "  • viz4 (Frameless)    - No title bar (immersive), shares viz1's scene" << std::endl;
    std::cout << "\nviz1, viz2, and viz4 share the same scene data (box + sphere)." << std::endl;
    std::cout << "viz3 has its own independent scene (cylinder + cone + points)." << std::endl;
    std::cout << "\nPress Enter to exit..." << std::endl;
    std::cout << std::string(70, '=') << std::endl;

    std::cin.get();

    // Cleanup all views before exit
    std::cout << "\n[8] Cleaning up..." << std::endl;
    viz1->close();
    viz2->close();
    viz3->close();
    viz4->close();
    std::cout << "    ✓ All views closed" << std::endl;
    std::cout << "\nDone." << std::endl;

    return 0;
}
