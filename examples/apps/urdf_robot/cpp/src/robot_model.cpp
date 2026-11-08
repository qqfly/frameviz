/**
 * @file robot_model.cpp
 * @brief Synthetic Six-Axis Arm robot model implementation
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#include "urdf_robot/robot_model.hpp"

namespace urdf_robot {

RobotModel::RobotModel(const std::string& mesh_base_url, const std::string& mesh_extension) {
    // Initialize joint angles to zero
    joint_angles_.fill(0.0);

    // Define links (base + 6 moving links)
    links_ = {
        {"base_link", mesh_base_url + "/base_link." + mesh_extension},
        {"link_1", mesh_base_url + "/link_1." + mesh_extension},
        {"link_2", mesh_base_url + "/link_2." + mesh_extension},
        {"link_3", mesh_base_url + "/link_3." + mesh_extension},
        {"link_4", mesh_base_url + "/link_4." + mesh_extension},
        {"link_5", mesh_base_url + "/link_5." + mesh_extension},
        {"link_6", mesh_base_url + "/link_6." + mesh_extension},
    };

    // Define joints (from Synthetic Six-Axis Arm URDF)
    joints_ = {
        {
            "joint_1", "base_link", "link_1",
            {0, 0, 0.3991},  // origin_xyz
            {0, 0, 0},       // origin_rpy
            {0, 0, 1},       // axis
            -2.967, 2.967    // limits
        },
        {
            "joint_2", "link_1", "link_2",
            {0, 0, 0},
            {0, 0, 0},
            {0, 1, 0},
            -1.745, 2.269
        },
        {
            "joint_3", "link_2", "link_3",
            {0, 0, 0.448},
            {0, 0, 0},
            {0, 1, 0},
            -3.491, 1.222
        },
        {
            "joint_4", "link_3", "link_4",
            {0, 0, 0.042},
            {0, 0, 0},
            {1, 0, 0},
            -4.712, 4.712
        },
        {
            "joint_5", "link_4", "link_5",
            {0.451, 0, 0},
            {0, 0, 0},
            {0, 1, 0},
            -2.269, 2.269
        },
        {
            "joint_6", "link_5", "link_6",
            {0.082, 0, 0},
            {0, 0, 0},
            {1, 0, 0},
            -6.283, 6.283
        },
    };
}

void RobotModel::setJointAngles(const JointAngles& angles) {
    joint_angles_ = angles;
}

void RobotModel::home() {
    joint_angles_.fill(0.0);
}

std::vector<Pose> RobotModel::forwardKinematics() const {
    std::vector<Pose> poses;
    poses.reserve(7);

    // Start at origin
    Vec3 current_pos;
    Mat3 current_rot = Mat3::identity();

    // Base link pose (at origin)
    Pose base_pose;
    base_pose.pos = current_pos;
    base_pose.quat = current_rot.toQuaternion();
    poses.push_back(base_pose);

    // Compute pose for each link
    for (size_t i = 0; i < joints_.size(); ++i) {
        const auto& joint = joints_[i];

        // Apply origin translation (in current frame) and rotation
        Mat3 origin_rot = Mat3::fromRPY(
            joint.origin_rpy.x,
            joint.origin_rpy.y,
            joint.origin_rpy.z
        );
        current_pos = current_pos + current_rot * joint.origin_xyz;
        current_rot = current_rot * origin_rot;

        // Apply joint rotation
        Mat3 joint_rot = Mat3::fromAxisAngle(joint.axis, joint_angles_[i]);
        current_rot = current_rot * joint_rot;

        // Store pose
        Pose link_pose;
        link_pose.pos = current_pos;
        link_pose.quat = current_rot.toQuaternion();
        poses.push_back(link_pose);
    }

    return poses;
}

} // namespace urdf_robot
