/**
 * FrameViz C++ Example - Mesh Flat Shading vs Smooth Shading
 *
 * 对应 Python: examples/python/01_basic_primitives/use_mesh_smooth_shading.py
 */

#include <frameviz/viz.hpp>

#include <cmath>
#include <iostream>
#include <utility>
#include <vector>

using namespace frameviz;

namespace {

std::pair<std::vector<float>, std::vector<uint32_t>> createUvSphere(
    float radius = 0.5f, int latSegments = 16, int lonSegments = 24) {
  constexpr float kPi = 3.14159265358979323846f;
  std::vector<float> vertices;
  std::vector<uint32_t> faces;
  vertices.reserve(static_cast<size_t>((latSegments + 1) * lonSegments * 3));
  faces.reserve(static_cast<size_t>(latSegments * lonSegments * 2 * 3));

  for (int i = 0; i <= latSegments; ++i) {
    const float theta = kPi * static_cast<float>(i) / static_cast<float>(latSegments);
    const float sinTheta = std::sin(theta);
    const float cosTheta = std::cos(theta);

    for (int j = 0; j < lonSegments; ++j) {
      const float phi = 2.0f * kPi * static_cast<float>(j) / static_cast<float>(lonSegments);
      const float x = radius * sinTheta * std::cos(phi);
      const float y = radius * sinTheta * std::sin(phi);
      const float z = radius * cosTheta;
      vertices.push_back(x);
      vertices.push_back(y);
      vertices.push_back(z);
    }
  }

  auto idx = [lonSegments](int i, int j) -> uint32_t {
    return static_cast<uint32_t>(i * lonSegments + (j % lonSegments));
  };

  for (int i = 0; i < latSegments; ++i) {
    for (int j = 0; j < lonSegments; ++j) {
      const uint32_t i0 = idx(i, j);
      const uint32_t i1 = idx(i, j + 1);
      const uint32_t i2 = idx(i + 1, j + 1);
      const uint32_t i3 = idx(i + 1, j);

      faces.push_back(i0);
      faces.push_back(i1);
      faces.push_back(i2);

      faces.push_back(i0);
      faces.push_back(i2);
      faces.push_back(i3);
    }
  }

  return {vertices, faces};
}

void offsetX(std::vector<float> &vertices, float xOffset) {
  for (size_t i = 0; i < vertices.size(); i += 3) {
    vertices[i] += xOffset;
  }
}

}  // namespace

int main() {
  std::cout << "======================================================\n";
  std::cout << "FrameViz C++ - Mesh Flat Shading vs Smooth Shading\n";
  std::cout << "======================================================\n";

  auto viz = Viz::open("ws://127.0.0.1:9527", "Mesh Smooth Shading Demo", 1200, 800);
  std::cout << "Connected: scene=" << viz->sceneId() << "\n";

  auto [vertices, faces] = createUvSphere();
  auto verticesFlat = vertices;
  auto verticesSmooth = vertices;
  offsetX(verticesFlat, -0.8f);
  offsetX(verticesSmooth, 0.8f);

  std::cout << "\n[1] Left: flat shading (smooth_shading=false)\n";
  auto hFlat = viz->addMesh(
      verticesFlat, faces, FacesFormat::TRI, {0.95f, 0.55f, 0.2f}, {},
      std::nullopt, false, false);
  std::cout << "    handle: " << hFlat << "\n";

  std::cout << "\n[2] Right: smooth shading (smooth_shading=true)\n";
  auto hSmooth = viz->addMesh(
      verticesSmooth, faces, FacesFormat::TRI, {0.95f, 0.55f, 0.2f}, {},
      std::nullopt, false, true);
  std::cout << "    handle: " << hSmooth << "\n";

  viz->setCameraPose({0.0f, -2.6f, 1.0f}, {0.0f, 0.0f, 0.0f}, {0.0f, 0.0f, 1.0f});

  std::cout << "\nObservation guide:\n";
  std::cout << "- Left sphere: highlights show faceted triangles\n";
  std::cout << "- Right sphere: highlights are smoother and more continuous\n";
  std::cout << "\nPress Enter to exit...\n";
  std::cin.get();

  viz->close();
  std::cout << "Connection closed\n";
  return 0;
}
