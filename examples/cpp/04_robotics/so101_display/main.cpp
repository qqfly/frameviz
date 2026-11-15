// Display the pinned SO-101 model with native joint controls. See the extra README.
#include <frameviz/viz.hpp>
#include "example_interrupt.hpp"
#include <cmath>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>

using namespace frameviz;
namespace fs = std::filesystem;

struct Joint {
    std::string name;
    Handle handle;
    RigidPose rest;
    Vec3 axis;
    std::array<float, 2> limits;

    RigidPose pose(float angle) const {
        const auto [x, y, z, w] = rest.quaternion;
        const auto [a, b, c] = axis;
        const auto s = std::sin(angle / 2);
        const auto t = std::cos(angle / 2);
        // Compose the rest orientation with the local hinge rotation (xyzw).
        return {rest.position, {w*a*s + x*t + y*c*s - z*b*s,
                                w*b*s - x*c*s + y*t + z*a*s,
                                w*c*s + x*b*s - y*a*s + z*t,
                                w*t - x*a*s - y*b*s - z*c*s}};
    }
};

RigidPose pose(const json &value) {
    return {value.at("position").get<Vec3>(), value.at("quaternion").get<Quat>()};
}

void addStl(Viz &viz, const fs::path &path, const Color &color, const SceneNodeOptions &node) {
    std::ifstream file(path, std::ios::binary);
    file.exceptions(std::ios::failbit | std::ios::badbit);
    file.seekg(80);
    auto word = [&]() {
        unsigned char data[4];
        file.read(reinterpret_cast<char *>(data), 4);
        return uint32_t(data[0]) | uint32_t(data[1]) << 8 | uint32_t(data[2]) << 16 | uint32_t(data[3]) << 24;
    };
    const auto count = word();
    if (!count || fs::file_size(path) != 84 + uint64_t(count) * 50) {
        throw std::runtime_error("Invalid SO-101 binary STL");
    }
    std::vector<float> vertices;
    std::vector<uint32_t> indices;
    vertices.reserve(size_t(count) * 9);
    indices.reserve(size_t(count) * 3);
    for (uint32_t i = 0; i < count; ++i) {
        file.seekg(12, std::ios::cur); // Skip the triangle normal.
        for (int j = 0; j < 9; ++j) {
            const auto bits = word();
            float coordinate;
            std::memcpy(&coordinate, &bits, sizeof(coordinate));
            vertices.push_back(coordinate);
        }
        for (uint32_t j = 0; j < 3; ++j) indices.push_back(i * 3 + j);
        file.seekg(2, std::ios::cur); // Skip the attribute field.
    }
    viz.addMesh(vertices, indices, FacesFormat::TRI, color, {}, std::nullopt, false, false, node);
}

void addBody(Viz &viz, const json &body, const fs::path &assets, std::vector<Joint> &joints,
             const std::optional<Handle> &parent = std::nullopt) {
    SceneNodeOptions node;
    node.parent = parent;
    node.name = body.at("name").get<std::string>();
    node.pose = pose(body.at("pose"));
    auto handle = viz.addNode(node);
    if (body.contains("joint")) {
        const auto &joint = body.at("joint");
        joints.push_back({joint.at("name"), handle, *node.pose, joint.at("axis"), joint.at("limits")});
    }
    node.parent = handle;
    for (const auto &item : body.at("geometry")) {
        node.pose = pose(item.at("pose"));
        const auto color = item.at("color").get<Color>();
        if (item.at("kind") == "mesh") {
            const fs::path name(item.at("file").get<std::string>());
            if (name.has_parent_path()) throw std::runtime_error("Invalid SO-101 mesh file name");
            addStl(viz, assets / name, color, node);
        } else if (item.at("kind") == "box") {
            viz.addBox(item.at("size"), {0, 0, 0}, {0, 0, 0, 1}, color, node);
        } else {
            viz.addCylinder(item.at("size").at(0).get<float>() / 2, item.at("size").at(1),
                            {0, 0, 0}, {0, 0, 0, 1}, color, node);
        }
    }
    for (const auto &child : body.at("children")) addBody(viz, child, assets, joints, handle);
}

int main(int argc, char **argv) {
    if (argc != 3) {
        std::cerr << "Usage: so101_display MODEL.json PINNED_ASSETS_DIRECTORY\n";
        return 2;
    }
    try {
        std::ifstream model(argv[1]);
        if (!model) throw std::runtime_error("Use so101_display.py --describe to generate MODEL.json");
        const frameviz::example::Interrupt interrupt;
        auto viz = Viz::open();
        std::vector<Joint> joints;
        addBody(*viz, json::parse(model), argv[2], joints);
        viz->setViewConfig({{"show_axes", false}});
        viz->setCameraPose({0.72f, -0.83f, 0.58f}, {0.08f, 0, 0.19f}, {0, 0, 1});
        const auto panel = viz->addWidget("group", "SO-101 joint angles");
        std::vector<Handle> controls;
        for (const auto &joint : joints) {
            const auto control = viz->addWidget("number", joint.name + " (rad)", 0,
                {{"parent", panel}, {"minimum", joint.limits[0]}, {"maximum", joint.limits[1]},
                 {"step", 0.01}, {"update_mode", "continuous"}});
            controls.push_back(control);
            viz->onWidgetChange(control, [&, joint](const json &event) {
                viz->setTransform(joint.handle, joint.pose(event.at("value").get<float>()));
            });
        }
        viz->onWidgetChange(viz->addWidget("button", "Reset pose", nullptr, {{"parent", panel}}),
            [&](const json &) {
                for (size_t i = 0; i < joints.size(); ++i) {
                    viz->setWidgetValue(controls[i], 0);
                    viz->setTransform(joints[i].handle, joints[i].rest);
                }
            });
        viz->setPickConfig({{"enabled", true}, {"mode", "object"}, {"button", 0}, {"ctrl_modifier", false}});
        viz->onEvent("picked", [](const json &event) {
            if (event.contains("name") && event["name"].is_string()) std::cout << event["name"] << std::endl;
        });
        std::cout << "SO-101 scene ready. Move a joint and try Reset pose. Enter to exit." << std::endl;
        if (!interrupt.waitForEnter(*viz)) return 130;
        viz->close();
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
