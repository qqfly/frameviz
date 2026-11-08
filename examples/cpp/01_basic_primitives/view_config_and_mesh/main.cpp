/**
 * FrameViz C++ Example - View Config + Mesh (TRI + POLY)
 *
 * 对应 Python: examples/python/01_basic_primitives/use_view_config_and_mesh.py
 */

#include <frameviz/viz.hpp>
#include <iostream>
#include <vector>

using namespace frameviz;

int main() {
    std::cout << "==================================================" << std::endl;
    std::cout << "FrameViz View Config + Mesh (TRI + POLY)" << std::endl;
    std::cout << "==================================================" << std::endl;

    // Open frameless window (immersive mode)
    // For normal window, set windowDecorations=true or omit the parameter
    auto viz = Viz::open("ws://127.0.0.1:9527", "FrameViz", 800, 600, false);
    std::cout << "[1] Connected (frameless window)" << std::endl;
    std::cout << "Press Enter to continue..." << std::endl;
    std::cin.get();

    std::cout << "[2] Setting view config..." << std::endl;
    json config = {
        {"show_grid", true},
        {"show_axes", true},
        {"background", {0.1f, 0.1f, 0.2f}}
    };
    viz->setViewConfig(config);
    std::cout << "    ✓ View config set" << std::endl;
    std::cout << "Press Enter to continue..." << std::endl;
    std::cin.get();

    std::cout << "[3] Add and clone boxes..." << std::endl;
    auto box = viz->addBox({0.2f, 0.2f, 0.2f}, {0, 0, 0.1f}, {0, 0, 0, 1}, {1, 0, 0});
    std::cin.get();

    auto clone_a = viz->cloneObject(box);
    auto clone_b = viz->cloneObject(box);
    auto clone_c = viz->cloneObject(box);

    viz->setTransform(clone_a, {0.4f, 0.0f, 0.1f}, {0, 0, 0, 1});
    viz->setTransform(clone_b, {0.0f, 0.4f, 0.1f}, {0, 0, 0, 1});
    viz->setTransform(clone_c, {0.4f, 0.4f, 0.1f}, {0, 0, 0, 1});

    std::cout << "    ✓ Cloned 3 boxes" << std::endl;
    std::cout << "Press Enter to continue..." << std::endl;
    std::cin.get();

    std::cout << "[4] Add TRI mesh (pyramid, per-face colors)..." << std::endl;
    std::vector<float> tri_vertices = {
        -0.8f, 0.0f, 0.0f,
        -0.4f, 0.0f, 0.0f,
        -0.4f, 0.4f, 0.0f,
        -0.8f, 0.4f, 0.0f,
        -0.6f, 0.2f, 0.4f,
    };
    std::vector<uint32_t> tri_faces = {
        0, 1, 2,
        0, 2, 3,
        0, 1, 4,
        1, 2, 4,
        2, 3, 4,
        3, 0, 4,
    };
    std::vector<Color> tri_face_colors = {
        {1.0f, 0.0f, 0.0f},
        {0.0f, 1.0f, 0.0f},
        {0.0f, 0.0f, 1.0f},
        {1.0f, 1.0f, 0.0f},
        {1.0f, 0.0f, 1.0f},
        {0.0f, 1.0f, 1.0f},
    };
    auto tri_mesh = viz->addMesh(tri_vertices, tri_faces, FacesFormat::TRI,
                                 {1.0f, 1.0f, 1.0f}, tri_face_colors);
    std::cout << "    ✓ TRI mesh handle: " << tri_mesh << std::endl;
    std::cout << "Press Enter to continue..." << std::endl;
    std::cin.get();

    std::cout << "[5] Add POLY mesh (cube, per-face colors)..." << std::endl;
    std::vector<float> poly_vertices = {
        0.2f, 0.0f, 0.0f,
        0.6f, 0.0f, 0.0f,
        0.6f, 0.4f, 0.0f,
        0.2f, 0.4f, 0.0f,
        0.2f, 0.0f, 0.4f,
        0.6f, 0.0f, 0.4f,
        0.6f, 0.4f, 0.4f,
        0.2f, 0.4f, 0.4f,
    };
    std::vector<uint32_t> poly_faces = {
        4, 0, 1, 2, 3,
        4, 4, 5, 6, 7,
        4, 0, 1, 5, 4,
        4, 3, 2, 6, 7,
        4, 0, 4, 7, 3,
        4, 1, 2, 6, 5
    };
    std::vector<Color> poly_face_colors = {
        {0.9f, 0.2f, 0.2f},
        {0.2f, 0.9f, 0.2f},
        {0.2f, 0.2f, 0.9f},
        {0.9f, 0.9f, 0.2f},
        {0.9f, 0.2f, 0.9f},
        {0.2f, 0.9f, 0.9f},
    };
    auto poly_mesh = viz->addMesh(poly_vertices, poly_faces, FacesFormat::POLY,
                                  {1.0f, 1.0f, 1.0f}, poly_face_colors);
    std::cout << "    ✓ POLY mesh handle: " << poly_mesh << std::endl;
    std::cout << "Press Enter to continue..." << std::endl;
    std::cin.get();

    std::cout << "[6] Get camera pose..." << std::endl;
    auto cam = viz->getCameraPose();
    std::cout << "    ✓ Camera eye: (" << cam.eye[0] << ", " << cam.eye[1]
              << ", " << cam.eye[2] << ")" << std::endl;
    std::cout << "Press Enter to continue..." << std::endl;
    std::cin.get();

    std::cout << "[7] Remove cloned objects..." << std::endl;
    viz->removeObjects({box, clone_a, clone_b, clone_c});
    std::cout << "    ✓ Removed" << std::endl;

    std::cout << "\nPress Enter to exit..." << std::endl;
    std::cin.get();

    viz->close();
    return 0;
}
