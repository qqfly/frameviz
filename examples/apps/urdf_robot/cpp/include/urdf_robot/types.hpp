/**
 * @file types.hpp
 * @brief Core type definitions for URDF Robot Backend
 *
 * Simple math types without external dependencies (no Eigen).
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#ifndef URDF_ROBOT_TYPES_HPP
#define URDF_ROBOT_TYPES_HPP

#include <array>
#include <cmath>
#include <string>

namespace urdf_robot {

// Joint angles for 6-DOF robot
using JointAngles = std::array<double, 6>;

/**
 * @brief Simple 3D vector.
 */
struct Vec3 {
    double x = 0.0, y = 0.0, z = 0.0;

    Vec3() = default;
    Vec3(double x_, double y_, double z_) : x(x_), y(y_), z(z_) {}

    Vec3 operator+(const Vec3& other) const {
        return {x + other.x, y + other.y, z + other.z};
    }

    Vec3 operator*(double s) const {
        return {x * s, y * s, z * s};
    }
};

/**
 * @brief Simple 3x3 matrix (row-major).
 */
struct Mat3 {
    double m[3][3] = {{1, 0, 0}, {0, 1, 0}, {0, 0, 1}};

    static Mat3 identity() {
        return Mat3();
    }

    // Matrix-vector multiplication
    Vec3 operator*(const Vec3& v) const {
        return {
            m[0][0] * v.x + m[0][1] * v.y + m[0][2] * v.z,
            m[1][0] * v.x + m[1][1] * v.y + m[1][2] * v.z,
            m[2][0] * v.x + m[2][1] * v.y + m[2][2] * v.z
        };
    }

    // Matrix-matrix multiplication
    Mat3 operator*(const Mat3& other) const {
        Mat3 result;
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                result.m[i][j] = 0;
                for (int k = 0; k < 3; ++k) {
                    result.m[i][j] += m[i][k] * other.m[k][j];
                }
            }
        }
        return result;
    }

    // Create rotation matrix around axis by angle (Rodrigues' formula)
    static Mat3 fromAxisAngle(const Vec3& axis, double angle) {
        double len = std::sqrt(axis.x * axis.x + axis.y * axis.y + axis.z * axis.z);
        if (len < 1e-10) return identity();

        double ax = axis.x / len, ay = axis.y / len, az = axis.z / len;
        double c = std::cos(angle);
        double s = std::sin(angle);
        double t = 1.0 - c;

        Mat3 r;
        r.m[0][0] = t * ax * ax + c;
        r.m[0][1] = t * ax * ay - s * az;
        r.m[0][2] = t * ax * az + s * ay;
        r.m[1][0] = t * ax * ay + s * az;
        r.m[1][1] = t * ay * ay + c;
        r.m[1][2] = t * ay * az - s * ax;
        r.m[2][0] = t * ax * az - s * ay;
        r.m[2][1] = t * ay * az + s * ax;
        r.m[2][2] = t * az * az + c;
        return r;
    }

    // Create rotation from RPY (roll-pitch-yaw, ZYX order)
    static Mat3 fromRPY(double roll, double pitch, double yaw) {
        Mat3 rx = fromAxisAngle({1, 0, 0}, roll);
        Mat3 ry = fromAxisAngle({0, 1, 0}, pitch);
        Mat3 rz = fromAxisAngle({0, 0, 1}, yaw);
        return rz * ry * rx;
    }

    // Convert rotation matrix to quaternion [x, y, z, w]
    std::array<double, 4> toQuaternion() const {
        double trace = m[0][0] + m[1][1] + m[2][2];
        double x, y, z, w;

        if (trace > 0) {
            double s = 0.5 / std::sqrt(trace + 1.0);
            w = 0.25 / s;
            x = (m[2][1] - m[1][2]) * s;
            y = (m[0][2] - m[2][0]) * s;
            z = (m[1][0] - m[0][1]) * s;
        } else if (m[0][0] > m[1][1] && m[0][0] > m[2][2]) {
            double s = 2.0 * std::sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]);
            w = (m[2][1] - m[1][2]) / s;
            x = 0.25 * s;
            y = (m[0][1] + m[1][0]) / s;
            z = (m[0][2] + m[2][0]) / s;
        } else if (m[1][1] > m[2][2]) {
            double s = 2.0 * std::sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]);
            w = (m[0][2] - m[2][0]) / s;
            x = (m[0][1] + m[1][0]) / s;
            y = 0.25 * s;
            z = (m[1][2] + m[2][1]) / s;
        } else {
            double s = 2.0 * std::sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]);
            w = (m[1][0] - m[0][1]) / s;
            x = (m[0][2] + m[2][0]) / s;
            y = (m[1][2] + m[2][1]) / s;
            z = 0.25 * s;
        }
        return {x, y, z, w};
    }
};

/**
 * @brief Pose (position + quaternion).
 */
struct Pose {
    Vec3 pos;
    std::array<double, 4> quat = {0, 0, 0, 1};  // [x, y, z, w]
};

/**
 * @brief Joint information from URDF.
 */
struct JointInfo {
    std::string name;
    std::string parent_link;
    std::string child_link;
    Vec3 origin_xyz;
    Vec3 origin_rpy;  // roll, pitch, yaw
    Vec3 axis;
    double limit_lower;
    double limit_upper;
};

/**
 * @brief Link information from URDF.
 */
struct LinkInfo {
    std::string name;
    std::string mesh_url;
};

/**
 * @brief Configuration for the backend.
 */
struct Config {
    std::string model_path;
    int ui_port = 9620;
    int asset_port = 8081;
};

} // namespace urdf_robot

#endif // URDF_ROBOT_TYPES_HPP
