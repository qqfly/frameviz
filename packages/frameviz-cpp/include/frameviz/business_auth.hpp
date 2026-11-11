#pragma once
// Local example business channel. The first frame or legacy upgrade header
// authenticates the session before business state or commands are exchanged.
#include <ixwebsocket/IXWebSocket.h>
#include <ixwebsocket/IXWebSocketMessageType.h>
#include <nlohmann/json.hpp>
#include <chrono>
#include <cstdlib>
#include <mutex>
#include <regex>
#include <sstream>
#include <unordered_map>

namespace frameviz {
class BusinessAuth {
  struct Session {
    std::chrono::steady_clock::time_point start;
    unsigned count = 0;
    bool authenticated = false;
  };
  std::mutex mutex_;
  std::unordered_map<ix::WebSocket*, Session> sessions_;
  static bool matches(const std::string& token, const std::string& expected) {
    unsigned mismatch = token.size() == expected.size() ? 0 : 1;
    for (size_t i = 0; i < expected.size(); ++i)
      mismatch |= expected[i] ^ (i < token.size() ? token[i] : 0);
    return expected.size() >= 32 && mismatch == 0;
  }

public:
  bool authorized(ix::WebSocket* socket) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = sessions_.find(socket);
    return it != sessions_.end() && it->second.authenticated;
  }
  bool accept(ix::WebSocket& socket, const ix::WebSocketMessagePtr& message) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (message->type == ix::WebSocketMessageType::Close || message->type == ix::WebSocketMessageType::Error) {
      sessions_.erase(&socket); return false;
    }
    if (message->type == ix::WebSocketMessageType::Open) {
      auto header = [&](const std::string& name) {
        for (const auto& entry : message->openInfo.headers) {
          auto key = entry.first;
          for (auto& c : key) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
          if (key == name) return entry.second;
        }
        return std::string();
      };
      const auto origin = header("origin");
      const char* env = std::getenv("FRAMEVIZ_BUSINESS_TOKEN");
      const std::string expected = env ? env : "";
      std::string token, part;
      unsigned found = 0;
      const auto offered = header("sec-websocket-protocol");
      std::istringstream protocols(offered);
      while (std::getline(protocols, part, ',')) {
        auto first = part.find_first_not_of(" \t"), last = part.find_last_not_of(" \t");
        if (first == std::string::npos) continue;
        part = part.substr(first, last - first + 1);
        if (part.rfind("token.", 0) == 0) { token = part.substr(6); ++found; }
      }
      const bool originOk = origin.empty() || std::regex_match(origin, std::regex(R"((http|https|tauri)://(localhost|127\.0\.0\.1|\[::1\]|tauri\.localhost)(:[0-9]+)?)"));
      const bool legacy = !offered.empty();
      if (expected.size() < 32 || (legacy && (found != 1 || !matches(token, expected)))
          || !originOk || sessions_.size() >= 32) {
        socket.close(1008, "Business authentication required"); return false;
      }
      sessions_[&socket] = {std::chrono::steady_clock::now(), 0, legacy};
      return legacy;
    }
    if (message->type != ix::WebSocketMessageType::Message) return false;
    auto it = sessions_.find(&socket);
    if (it == sessions_.end()) return false;
    auto now = std::chrono::steady_clock::now();
    if (!it->second.authenticated) {
      using nlohmann::json;
      const auto payload = !message->binary && message->str.size() <= 65536
          ? json::parse(message->str, nullptr, false) : json();
      const char* expected = std::getenv("FRAMEVIZ_BUSINESS_TOKEN");
      if (!expected || now - it->second.start > std::chrono::seconds(3) ||
          !payload.is_object() || !payload.contains("type") || payload["type"] != "auth" ||
          !payload.contains("token") || !payload["token"].is_string() || !matches(payload["token"].get<std::string>(), expected)) {
        sessions_.erase(it);
        socket.close(1008, "Business authentication required");
        return false;
      }
      it->second = {now, 0, true};
      socket.sendText(R"({"type":"auth_ok"})");
      return false;
    }
    if (now - it->second.start >= std::chrono::seconds(1)) it->second = {now, 0, true};
    if (message->binary || message->str.size() > 65536 || ++it->second.count > 120) {
      sessions_.erase(it); socket.close(1008, "Business message limit exceeded"); return false;
    }
    return true;
  }
};
}
