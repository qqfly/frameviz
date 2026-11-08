/**
 * @file robot_visualizer.cpp
 * @brief Robot visualization wrapper implementation
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#include "urdf_robot/robot_visualizer.hpp"
#include <iostream>
#include <thread>
#include <chrono>

namespace urdf_robot {

RobotVisualizer::RobotVisualizer(
    std::shared_ptr<frameviz::Viz> viz,
    const std::string& mesh_base_url,
    const std::string& mesh_extension,
    const std::optional<std::array<float, 4>>& color
)
    : viz_(viz), robot_(mesh_base_url, mesh_extension), color_(color) {
}

void RobotVisualizer::loadMeshes() {
    // Clear the scene first
    viz_->clear();

    // Load all link meshes
    handles_.clear();
    for (const auto& link : robot_.links()) {
        std::string handle;

        if (color_) {
            // Convert array to vector for FrameViz Color type
            std::vector<float> color_vec = {
                (*color_)[0], (*color_)[1], (*color_)[2], (*color_)[3]
            };

            // Load with color
            handle = viz_->loadMesh(
                link.mesh_url,
                {0.0f, 0.0f, 0.0f},  // pos
                {0.0f, 0.0f, 0.0f, 1.0f},  // quat
                {1.0f, 1.0f, 1.0f},  // scale
                color_vec  // RGBA color
            );
        } else {
            // Load without color (use original mesh colors)
            handle = viz_->loadMesh(
                link.mesh_url,
                {0.0f, 0.0f, 0.0f},  // pos
                {0.0f, 0.0f, 0.0f, 1.0f},  // quat
                {1.0f, 1.0f, 1.0f}  // scale
            );
        }

        handles_.push_back(handle);
        std::cout << "[Backend] Loaded: " << link.name << " -> " << handle << std::endl;

        // Small delay to avoid overwhelming the renderer
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }

    std::cout << "[Backend] Loaded " << handles_.size() << " robot links" << std::endl;
}

void RobotVisualizer::updateVisuals() {
    auto poses = robot_.forwardKinematics();

    // Sanity check
    if (handles_.size() != poses.size()) {
        std::cerr << "[Backend] Warning: handle count mismatch" << std::endl;
        return;
    }

    // Update all link transforms
    for (size_t i = 0; i < handles_.size() && i < poses.size(); ++i) {
        const auto& p = poses[i];
        viz_->setTransform(
            handles_[i],
            {static_cast<float>(p.pos.x),
             static_cast<float>(p.pos.y),
             static_cast<float>(p.pos.z)},
            {static_cast<float>(p.quat[0]),
             static_cast<float>(p.quat[1]),
             static_cast<float>(p.quat[2]),
             static_cast<float>(p.quat[3])}
        );
    }
}

void RobotVisualizer::setJointAngles(const JointAngles& angles) {
    robot_.setJointAngles(angles);
    updateVisuals();
}

} // namespace urdf_robot
