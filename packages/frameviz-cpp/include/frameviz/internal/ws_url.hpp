#pragma once

// Keep this compatibility header for internal includes.
// resolveWsUrl is declared in frameviz/discovery.hpp.
#include "frameviz/discovery.hpp"

namespace frameviz::detail {
std::optional<DiscoveryInfo> runningLocalHost();
bool isLocalWsUrl(const std::string &url);
bool hasDesktop();
std::string startLocalHost(const std::string &url, double timeout, bool headless,
                           bool automaticEndpoint);
}
