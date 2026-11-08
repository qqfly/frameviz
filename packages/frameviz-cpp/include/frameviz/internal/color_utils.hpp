/**
 * @file color_utils.hpp
 * @brief Internal color helpers for FrameViz C++ SDK.
 *
 * @note This header is for internal/testing use only.
 */

#ifndef FRAMEVIZ_CPP_INTERNAL_COLOR_UTILS_HPP
#define FRAMEVIZ_CPP_INTERNAL_COLOR_UTILS_HPP

#include <cmath>
#include <cstdint>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#include "frameviz/types.hpp"

namespace frameviz::detail {

inline void validateColorComponents(const Color &c,
                                    const std::string &label,
                                    bool allow_alpha = true) {
  if (allow_alpha) {
    if (c.size() != 3 && c.size() != 4) {
      throw std::runtime_error(label + " must have exactly 3 or 4 components");
    }
  } else if (c.size() != 3) {
    throw std::runtime_error(label + " must have exactly 3 components");
  }
  for (size_t i = 0; i < 3; ++i) {
    if (c[i] < 0.0f || c[i] > 1.0f) {
      throw std::runtime_error(label + " components must be in [0.0, 1.0]");
    }
  }
  if (c.size() == 4) {
    if (c[3] < 0.0f || c[3] > 1.0f) {
      throw std::runtime_error(label + " alpha must be in [0.0, 1.0]");
    }
  }
}

inline uint8_t colorToByte(float value) {
  if (value < 0.0f || value > 1.0f) {
    throw std::runtime_error("color components must be in [0.0, 1.0]");
  }
  return static_cast<uint8_t>(std::lround(value * 255.0f));
}

inline std::vector<uint8_t> packColorsToU8(
    const std::vector<Color> &colors,
    const std::string &label,
    std::optional<size_t> expected_count = std::nullopt) {
  if (expected_count.has_value() && colors.size() != expected_count.value()) {
    throw std::runtime_error(label + " size must match element count");
  }
  std::vector<uint8_t> packed;
  packed.reserve(colors.size() * 3);
  for (const auto &c : colors) {
    validateColorComponents(c, label, false);
    packed.push_back(colorToByte(c[0]));
    packed.push_back(colorToByte(c[1]));
    packed.push_back(colorToByte(c[2]));
  }
  return packed;
}

} // namespace frameviz::detail

#endif // FRAMEVIZ_CPP_INTERNAL_COLOR_UTILS_HPP
