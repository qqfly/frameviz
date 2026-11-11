#include <frameviz/viz.hpp>

#include <cmath>
#include <iostream>
#include <stdexcept>

using namespace frameviz;

void require(bool condition, const char *message) {
  if (!condition) throw std::runtime_error(message);
}

void requirePosition(const Vec3 &position, const Vec3 &expected) {
  for (size_t axis = 0; axis < position.size(); ++axis)
    require(std::abs(position[axis] - expected[axis]) < 1e-5f, "Unexpected position");
}

int main(int argc, char **argv) {
  if (argc != 3) return 2;
  try {
    auto viz = Viz::connect(argv[1], argv[2]);
    SceneNodeOptions root;
    root.pose = RigidPose::fromArray({3, 4, 0, 0, 0, 1, 1});
    root.name = "joint";
    auto joint = viz->addNode(root);
    viz->setGeometryScale(joint, {10, 20, 30});

    SceneNodeOptions child;
    child.parent = joint;
    child.pose = RigidPose{{2, 0, 0}};
    auto box = viz->addBox({1, 1, 1}, {}, {0, 0, 0, 1}, {0, 1, 0}, child);
    viz->setObjectMetadata(box, "link", {{"role", "demo"}});
    requirePosition(viz->getTransform(box, TransformSpace::World).pos, {3, 6, 0});
    auto matrix = viz->getTransformMatrix(box, TransformSpace::World);
    require(std::abs(matrix[13] - 6) < 1e-5, "Incorrect rigid world matrix");
    viz->setParent(box, std::nullopt);
    requirePosition(viz->getTransform(box).pos, {3, 6, 0});
    viz->setParent(box, joint, RigidPose{{1, 0, 0}});
    requirePosition(viz->getTransform(box, TransformSpace::World).pos, {3, 5, 0});

    std::vector<float> points(500001 * 3, 1.0f);
    auto invalid = child;
    invalid.parent = "missing";
    bool rejected = false;
    try {
      viz->addPoints(points, Color{1, 1, 1}, 2, invalid);
    } catch (const std::runtime_error &error) {
      rejected = std::string(error.what()).find("Parent") != std::string::npos;
    }
    require(rejected, "Missing point cloud parent must be rejected");
    auto cloud = viz->addPoints(points, Color{1, 1, 1}, 2, child);
    viz.reset();
    auto again = Viz::connect(argv[1], argv[2]);
    requirePosition(again->getTransform(cloud, TransformSpace::World).pos, {3, 6, 0});
    again->setVisible(cloud, false);
    std::cout << cloud << '\n';
    return 0;
  } catch (const std::exception &error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
