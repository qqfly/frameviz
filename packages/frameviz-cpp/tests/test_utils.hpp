#pragma once

#include <frameviz/internal/ws_url.hpp>
#include <string>

namespace frameviz::testutil {

inline std::string resolveTestWsUrl() {
  return resolveWsUrl("ws://127.0.0.1:9527");
}

} // namespace frameviz::testutil
