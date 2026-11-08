/**
 * @file robot_model.hpp
 * @brief Synthetic Six-Axis Arm robot model with forward kinematics
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#ifndef URDF_ROBOT_ROBOT_MODEL_HPP
#define URDF_ROBOT_ROBOT_MODEL_HPP

#include "types.hpp"
#include <vector>

namespace urdf_robot {

/**
 * @brief Synthetic Six-Axis Arm robot model with forward kinematics.
 *
 * This class implements the kinematic model of the Synthetic Six-Axis Arm robot,
 * computing link poses from joint angles.
 */
class RobotModel {
public:
    /**
     * @brief Construct a robot model with mesh URLs.
     * @param mesh_base_url Base URL for mesh files (e.g., "http://localhost:8081/meshes/visual")
     * @param mesh_extension File extension for meshes (e.g., "dae" or "stl")
     */
    RobotModel(const std::string& mesh_base_url, const std::string& mesh_extension);

    /**
     * @brief Get all link information.
     * @return Vector of LinkInfo for all 7 links (base + 6 moving links)
     */
    const std::vector<LinkInfo>& links() const { return links_; }

    /**
     * @brief Get all joint information.
     * @return Vector of JointInfo for all 6 joints
     */
    const std::vector<JointInfo>& joints() const { return joints_; }

    /**
     * @brief Get current joint angles.
     * @return Current joint angles in radians
     */
    const JointAngles& jointAngles() const { return joint_angles_; }

    /**
     * @brief Set joint angles.
     * @param angles Joint angles in radians (6 values)
     */
    void setJointAngles(const JointAngles& angles);

    /**
     * @brief Compute forward kinematics.
     * @return Vector of 7 Poses (base_link + link_1 through link_6)
     */
    std::vector<Pose> forwardKinematics() const;

    /**
     * @brief Reset all joints to home position (all zeros).
     */
    void home();

private:
    std::vector<LinkInfo> links_;
    std::vector<JointInfo> joints_;
    JointAngles joint_angles_;
};

} // namespace urdf_robot

#endif // URDF_ROBOT_ROBOT_MODEL_HPP
