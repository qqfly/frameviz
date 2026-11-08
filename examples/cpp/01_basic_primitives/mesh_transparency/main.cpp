/**
 * FrameViz C++ Example - Mesh Transparency and Wireframe
 *
 * Demonstrates:
 * - Using alpha parameter to control mesh transparency
 * - Using wireframe parameter to control edge visibility
 */

#include <frameviz/viz.hpp>
#include <iostream>

using namespace frameviz;

int main() {
    std::cout << "======================================================\n";
    std::cout << "FrameViz C++ - Mesh Transparency and Wireframe Demo\n";
    std::cout << "======================================================\n";

    auto viz = Viz::open("ws://127.0.0.1:9527", "Mesh Transparency Demo", 1000, 800);
    std::cout << "\nConnected: scene=" << viz->sceneId() << "\n";

    // Cube vertices (8 corners)
    std::vector<float> vertices = {
        0, 0, 0,  // 0: left-bottom-front
        1, 0, 0,  // 1: right-bottom-front
        1, 1, 0,  // 2: right-top-front
        0, 1, 0,  // 3: left-top-front
        0, 0, 1,  // 4: left-bottom-back
        1, 0, 1,  // 5: right-bottom-back
        1, 1, 1,  // 6: right-top-back
        0, 1, 1,  // 7: left-top-back
    };

    // 12 triangles (6 faces, 2 triangles per face)
    std::vector<uint32_t> faces = {
        // Front face (z=0)
        0, 1, 2, 0, 2, 3,
        // Back face (z=1)
        5, 4, 7, 5, 7, 6,
        // Bottom face (y=0)
        4, 5, 1, 4, 1, 0,
        // Top face (y=1)
        3, 2, 6, 3, 6, 7,
        // Left face (x=0)
        4, 0, 3, 4, 3, 7,
        // Right face (x=1)
        1, 5, 6, 1, 6, 2,
    };

    // ─────────────────────────────────────────────────────────────────────────
    // Demo 1: Alpha Transparency Control
    // ─────────────────────────────────────────────────────────────────────────
    std::cout << "\n[1] Adding three cubes with different alpha values...\n";

    // Opaque red cube (alpha=1.0)
    viz->addMesh(vertices, faces, FacesFormat::TRI, {1, 0, 0}, {}, 1.0f, false);
    std::cout << "    ✓ Red cube:   alpha=1.0 (opaque)\n";

    // Semi-transparent green cube (alpha=0.5)
    std::vector<float> vertices2 = vertices;
    for (size_t i = 0; i < vertices2.size(); i += 3) {
        vertices2[i] += 1.5f;  // offset x
    }
    viz->addMesh(vertices2, faces, FacesFormat::TRI, {0, 1, 0}, {}, 0.5f, false);
    std::cout << "    ✓ Green cube: alpha=0.5 (semi-transparent)\n";

    // Highly transparent blue cube (alpha=0.3)
    std::vector<float> vertices3 = vertices;
    for (size_t i = 0; i < vertices3.size(); i += 3) {
        vertices3[i] += 3.0f;  // offset x
    }
    viz->addMesh(vertices3, faces, FacesFormat::TRI, {0, 0, 1}, {}, 0.3f, false);
    std::cout << "    ✓ Blue cube:  alpha=0.3 (highly transparent)\n";

    // ─────────────────────────────────────────────────────────────────────────
    // Demo 2: Wireframe Edge Control
    // ─────────────────────────────────────────────────────────────────────────
    std::cout << "\n[2] Adding two cubes, with and without wireframe...\n";

    // Yellow cube without wireframe (wireframe=false)
    std::vector<float> vertices4 = vertices;
    for (size_t i = 0; i < vertices4.size(); i += 3) {
        vertices4[i + 1] += 1.5f;  // offset y
    }
    viz->addMesh(vertices4, faces, FacesFormat::TRI, {1, 1, 0}, {}, std::nullopt, false);
    std::cout << "    ✓ Yellow cube:  wireframe=false (no edges)\n";

    // Magenta cube with wireframe (wireframe=true)
    std::vector<float> vertices5 = vertices;
    for (size_t i = 0; i < vertices5.size(); i += 3) {
        vertices5[i] += 1.5f;      // offset x
        vertices5[i + 1] += 1.5f;  // offset y
    }
    viz->addMesh(vertices5, faces, FacesFormat::TRI, {1, 0, 1}, {}, std::nullopt, true);
    std::cout << "    ✓ Magenta cube: wireframe=true (shows black edges)\n";

    // ─────────────────────────────────────────────────────────────────────────
    // Demo 3: Combined alpha + wireframe
    // ─────────────────────────────────────────────────────────────────────────
    std::cout << "\n[3] Adding cube with both alpha and wireframe...\n";

    // Cyan cube: transparent + wireframe
    std::vector<float> vertices6 = vertices;
    for (size_t i = 0; i < vertices6.size(); i += 3) {
        vertices6[i] += 3.0f;      // offset x
        vertices6[i + 1] += 1.5f;  // offset y
    }
    viz->addMesh(vertices6, faces, FacesFormat::TRI, {0, 1, 1}, {}, 0.6f, true);
    std::cout << "    ✓ Cyan cube: alpha=0.6, wireframe=true (transparent with edges)\n";

    // ─────────────────────────────────────────────────────────────────────────
    // Set camera
    // ─────────────────────────────────────────────────────────────────────────
    viz->setCameraPose({2, 2, 4}, {1.5, 0.75, 0.5}, {0, 0, 1});

    std::cout << "\n" << std::string(70, '=');
    std::cout << "\n✓ Rendering complete!\n";
    std::cout << "\nObservation guide:\n";
    std::cout << "  Row 1 (Alpha Transparency):\n";
    std::cout << "    - Red cube is completely opaque\n";
    std::cout << "    - Green cube is semi-transparent (50% opacity)\n";
    std::cout << "    - Blue cube is highly transparent (30% opacity)\n";
    std::cout << "\n  Row 2 (Wireframe Edges):\n";
    std::cout << "    - Yellow cube has smooth surfaces without edge lines\n";
    std::cout << "    - Magenta cube shows black semi-transparent edge lines\n";
    std::cout << "\n  Row 3 (Combined):\n";
    std::cout << "    - Cyan cube combines transparency with wireframe edges\n";
    std::cout << "\n" << std::string(70, '=');
    std::cout << "\nPress Enter to exit...\n";
    std::cout << std::string(70, '=') << '\n';

    std::cin.get();

    viz->close();
    std::cout << "\n✓ Connection closed\n";

    return 0;
}
