#pragma once
#include "types.hpp"
#include <optional>
#include <regex>

namespace frameviz {
inline std::optional<std::array<int,3>> parseProtocolVersion(const std::string& value) {
  static const std::regex pattern(R"((0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8}))");
  std::smatch match;
  if (!std::regex_match(value,match,pattern)) return std::nullopt;
  return std::array<int,3>{std::stoi(match[1]),std::stoi(match[2]),std::stoi(match[3])};
}
inline bool isProtocolCompatible(const std::string& remote, const std::string& local=PROTOCOL_VERSION) {
  auto a=parseProtocolVersion(remote), b=parseProtocolVersion(local);
  return a && b && (*a)[0]==(*b)[0] && (*a)[1]==(*b)[1];
}
inline std::string hostVersionError(const std::string& remote, const std::string& local=PROTOCOL_VERSION) {
  auto a=parseProtocolVersion(remote), b=parseProtocolVersion(local);
  if (!a || !b) return "Missing or malformed protocol version; install matching FrameViz runtime and C++ SDK.";
  if (isProtocolCompatible(remote,local)) return "";
  if (std::array<int,2>{(*a)[0],(*a)[1]} < std::array<int,2>{(*b)[0],(*b)[1]})
    return "Host protocol "+remote+" is older than SDK "+local+". Upgrade the FrameViz runtime.";
  return "Host protocol "+remote+" is newer than SDK "+local+". Upgrade the C++ SDK.";
}
}
