/**
 * @file buffer.cpp
 * @brief Buffer upload utilities for FrameViz C++ SDK
 *
 * Maintainer: qqfly
 * @date 2026-01-25
 * @bug No known bugs
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#include "frameviz/viz.hpp"

#include <cstring>
#include <stdexcept>
#include <vector>

namespace frameviz {

BufferRef Viz::uploadBuffer(const void *data, size_t size_bytes,
                            const std::string &dtype,
                            const std::vector<int> &shape) {
  // Create buffer
  json create_args = {
      {"size_bytes", size_bytes}, {"dtype", dtype}, {"shape", shape}};

  json create_result = m_client->sendCommand("create_buffer", create_args);
  std::string buffer_id = create_result["buffer_id"];

  // Upload in chunks (16MB per chunk)
  const size_t CHUNK_SIZE = 16 * 1024 * 1024;
  const uint8_t *data_ptr = static_cast<const uint8_t *>(data);

  for (size_t offset = 0; offset < size_bytes; offset += CHUNK_SIZE) {
    size_t chunk_bytes = std::min(CHUNK_SIZE, size_bytes - offset);

    std::vector<uint8_t> chunk_data(data_ptr + offset,
                                    data_ptr + offset + chunk_bytes);

    json upload_args = {{"buffer_id", buffer_id},
                        {"offset_bytes", offset},
                        {"chunk_bytes", chunk_bytes}};

    m_client->sendCommandWithBinary("upload_buffer_chunk", upload_args,
                                    chunk_data);
  }

  return BufferRef{buffer_id, dtype, shape};
}

} // namespace frameviz
