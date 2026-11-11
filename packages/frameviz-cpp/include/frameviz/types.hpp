/**
 * @file types.hpp
 * @brief Core type definitions for FrameViz C++ SDK
 *
 * Maintainer: qqfly
 * @date 2026-01-25
 * @bug No known bugs
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#ifndef FRAMEVIZ_CPP_TYPES_HPP
#define FRAMEVIZ_CPP_TYPES_HPP

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace frameviz
{

// Protocol version
constexpr const char *PROTOCOL_VERSION = "0.4.0";
constexpr const char *MIN_COMPATIBLE_VERSION = "0.4.0";
constexpr int DEFAULT_WS_PORT = 9527;

// Handle type (string-based, consistent with Python SDK)
using Handle = std::string;

// 3D vector type
using Vec3 = std::array<float, 3>;

// Quaternion type [qx, qy, qz, qw]
using Quat = std::array<float, 4>;

// Color type [r, g, b] or [r, g, b, a], values in 0..1
using Color = std::vector<float>;

// Rigid scene-tree pose. Quaternion components are always xyzw.
struct RigidPose {
    Vec3 position{0, 0, 0};
    Quat quaternion{0, 0, 0, 1};

    static RigidPose fromArray(const std::array<float, 7> &values) {
        return {{values[0], values[1], values[2]},
                {values[3], values[4], values[5], values[6]}};
    }
};

enum class TransformSpace { Local, World };

// Legacy pose. Scale refers to the object's own geometry.
struct Pose {
    Vec3 pos{0.0f, 0.0f, 0.0f};
    Quat quat{0.0f, 0.0f, 0.0f, 1.0f};
    Vec3 scale{1.0f, 1.0f, 1.0f};
};

// Camera pose
struct CameraPose {
    Vec3 eye{5.0f, 5.0f, 5.0f};
    Vec3 target{0.0f, 0.0f, 0.0f};
    Vec3 up{0.0f, 0.0f, 1.0f};
};

// Buffer reference for binary data
struct BufferRef {
    std::string buffer_id;
    std::string dtype; // "f32", "u32", "u16", "u8"
    std::vector<int> shape;
};

// Transform item for batch operations
struct TransformItem {
    Handle handle;
    Pose pose;
};

// Instance type
enum class InstanceType { BOX, SPHERE, AXES };

// Faces format for mesh
enum class FacesFormat {
    TRI, // Triangle indices [F, 3]
    POLY // Polygon format: {m,k1..km,n,p1..pn,...}
};

// Error codes
enum class ErrorCode {
    OK = 0,
    CONNECTION_FAILED,
    CONNECTION_TIMEOUT,
    COMMAND_TIMEOUT,
    PROTOCOL_ERROR,
    INVALID_ARGS,
    UNKNOWN_COMMAND,
    INTERNAL_ERROR
};

} // namespace frameviz

#endif // FRAMEVIZ_CPP_TYPES_HPP
