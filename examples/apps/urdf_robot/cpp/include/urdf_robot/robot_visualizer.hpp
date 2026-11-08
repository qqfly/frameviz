/**
 * @file robot_visualizer.hpp
 * @brief Robot visualization wrapper using FrameViz high-level API
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#ifndef URDF_ROBOT_ROBOT_VISUALIZER_HPP
#define URDF_ROBOT_ROBOT_VISUALIZER_HPP

#include "robot_model.hpp"
#include <frameviz/viz.hpp>
#include <memory>
#include <string>
#include <vector>
#include <optional>

namespace urdf_robot {

/**
 * @brief Robot visualizer using FrameViz high-level API.
 *
 * This class encapsulates the visualization logic for a robot,
 * matching the Python backend's RobotVisualizer pattern.
 */
class RobotVisualizer {
public:
    /**
     * @brief Construct a robot visualizer.
     *
     * @param viz FrameViz Viz instance (must be initialized)
     * @param mesh_base_url Base URL for mesh files
     * @param mesh_extension File extension for meshes (e.g., "dae" or "stl")
     * @param color Optional RGBA color [r, g, b, a] (0.0-1.0)
     */
    RobotVisualizer(
        std::shared_ptr<frameviz::Viz> viz,
        const std::string& mesh_base_url,
        const std::string& mesh_extension,
        const std::optional<std::array<float, 4>>& color = std::nullopt
    );

    /**
     * @brief Load all robot meshes into the scene.
     *
     * This method clears the scene and loads all link meshes.
     * After loading, call updateVisuals() to set initial poses.
     */
    void loadMeshes();

    /**
     * @brief Update visual transforms based on current joint angles.
     *
     * Computes forward kinematics and updates all link transforms.
     */
    void updateVisuals();

    /**
     * @brief Set joint angles and update visuals.
     *
     * @param angles Joint angles in radians (6 values)
     */
    void setJointAngles(const JointAngles& angles);

    /**
     * @brief Get current joint angles.
     *
     * @return Current joint angles
     */
    const JointAngles& jointAngles() const { return robot_.jointAngles(); }

    /**
     * @brief Get the underlying robot model.
     *
     * @return Const reference to robot model
     */
    const RobotModel& robotModel() const { return robot_; }

private:
    std::shared_ptr<frameviz::Viz> viz_;
    RobotModel robot_;
    std::vector<std::string> handles_;
    std::optional<std::array<float, 4>> color_;
};

} // namespace urdf_robot

#endif // URDF_ROBOT_ROBOT_VISUALIZER_HPP
