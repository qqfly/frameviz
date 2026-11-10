#include <deque>
/**
 * @file client.cpp
 * @brief FrameVizClient implementation using ixwebsocket
 *
 * Maintainer: qqfly
 * @date 2026-01-25
 * @bug No known bugs
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#include "frameviz/client.hpp"
#include "frameviz/discovery.hpp"
#include "frameviz/protocol_version.hpp"

#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <iostream>
#include <mutex>
#include <queue>
#include <stdexcept>
#include <sstream>
#include <thread>
#include <tuple>
#include <unordered_set>
#include <vector>

#include <ixwebsocket/IXWebSocket.h>
#include <nlohmann/json.hpp>

namespace frameviz {

using json = nlohmann::json;

class FrameVizClient::Impl {
public:
  explicit Impl(const std::string &url)
      : m_url(url), m_connected(false), m_authenticated(false),
        m_requestId(0), m_timeout(std::chrono::seconds(10)), m_authOk(false) {}

  ~Impl() { close(); }

  void connect(std::chrono::seconds timeout) {
    if (m_connected) {
      return;
    }

    m_timeout = timeout;
    { std::lock_guard<std::mutex> guard(m_connectMutex); m_connectError.reset(); }
    m_authenticated = false;

    m_ws.setUrl(m_url);

    // Set up message handler
    m_ws.setOnMessageCallback(
        [this](const ix::WebSocketMessagePtr &msg) { handleMessage(msg); });

    // Start connection
    m_ws.start();

    // Wait for connection
    auto deadline = std::chrono::steady_clock::now() + timeout;

    std::unique_lock<std::mutex> lock(m_connectMutex);
    bool connected = m_connectCv.wait_until(lock, deadline, [this] {
      return m_connected.load() || m_connectError.has_value();
    });

    if (!connected) {
      lock.unlock();
      m_ws.stop();
      throw std::runtime_error("Connection timeout: " + m_url);
    }

    if (m_connectError.has_value()) {
      const auto error = *m_connectError;
      lock.unlock();
      m_ws.stop();
      throw std::runtime_error("Connection failed: " + error);
    }

    lock.unlock();
    // Authenticate after successful connection
    try {
      authenticate();
    } catch (const std::exception &e) {
      m_ws.stop();
      m_connected = false;
      throw std::runtime_error(std::string("Authentication failed: ") + e.what());
    }
  }

  void close() {
    m_ws.stop();
    m_connected = false;
    m_authenticated = false;
  }

  bool isConnected() const { return m_connected.load(); }

  json sendCommand(const std::string &name, const json &args) {
    if (!m_connected) {
      throw std::runtime_error("Not connected");
    }

    // Create command envelope
    std::string cmd_id;
    {
      std::lock_guard<std::mutex> lock(m_mutex);
      ++m_requestId;
      cmd_id = "c_" + std::to_string(m_requestId);
    }

    json envelope = {{"protocol_version", PROTOCOL_VERSION},
                     {"type", "cmd"},
                     {"id", cmd_id},
                     {"name", name},
                     {"args", args.is_null() ? json::object() : args}};

    // Register pending request
    auto wait_event = std::make_shared<std::condition_variable>();
    {
      std::lock_guard<std::mutex> lock(m_mutex);
      m_pending[cmd_id] = wait_event;
    }

    // Send command
    std::string msg_str = envelope.dump();
    { std::lock_guard<std::mutex> send_lock(m_sendMutex); m_ws.send(msg_str); }

    // Wait for response
    std::unique_lock<std::mutex> lock(m_mutex);
    bool received = wait_event->wait_for(lock, m_timeout, [this, &cmd_id] {
      return m_responses.find(cmd_id) != m_responses.end() || !m_connected;
    });

    // Cleanup pending
    m_pending.erase(cmd_id);

    if (!received || !m_connected) {
      throw std::runtime_error("Command '" + name + (m_connected ? "' timed out" : "' failed: connection closed"));
    }

    // Get response
    json response = std::move(m_responses[cmd_id]);
    m_responses.erase(cmd_id);

    // Check for errors
    if (!response.value("ok", false)) {
      auto error = response.value("error", json::object());
      std::string code = error.value("code", "UNKNOWN");
      std::string msg = error.value("message", "Command failed");
      throw std::runtime_error("[" + code + "] " + msg);
    }

    return response.value("result", json::object());
  }

  json sendCommandWithBinary(const std::string &name, const json &args,
                             const std::vector<uint8_t> &binary_data) {
    if (!m_connected) {
      throw std::runtime_error("Not connected");
    }

    // Create command envelope
    std::string cmd_id;
    {
      std::lock_guard<std::mutex> lock(m_mutex);
      ++m_requestId;
      cmd_id = "c_" + std::to_string(m_requestId);
    }

    json envelope = {{"protocol_version", PROTOCOL_VERSION},
                     {"type", "cmd"},
                     {"id", cmd_id},
                     {"name", name},
                     {"args", args.is_null() ? json::object() : args}};

    // Register pending request
    auto wait_event = std::make_shared<std::condition_variable>();
    {
      std::lock_guard<std::mutex> lock(m_mutex);
      m_pending[cmd_id] = wait_event;
    }

    // Send command followed by binary
    {
      std::lock_guard<std::mutex> send_lock(m_sendMutex);
      m_ws.send(envelope.dump());
      m_ws.sendBinary(std::string(binary_data.begin(), binary_data.end()));
    }

    // Wait for response
    std::unique_lock<std::mutex> lock(m_mutex);
    bool received = wait_event->wait_for(lock, m_timeout, [this, &cmd_id] {
      return m_responses.find(cmd_id) != m_responses.end() || !m_connected;
    });

    // Cleanup pending
    m_pending.erase(cmd_id);

    if (!received || !m_connected) {
      throw std::runtime_error("Command '" + name + (m_connected ? "' timed out" : "' failed: connection closed"));
    }

    // Get response
    json response = std::move(m_responses[cmd_id]);
    m_responses.erase(cmd_id);

    // Check for errors
    if (!response.value("ok", false)) {
      auto error = response.value("error", json::object());
      std::string code = error.value("code", "UNKNOWN");
      std::string msg = error.value("message", "Command failed");
      throw std::runtime_error("[" + code + "] " + msg);
    }

    return response.value("result", json::object());
  }

  void sendBinary(const std::vector<uint8_t> &data) {
    if (!m_connected) {
      throw std::runtime_error("Not connected");
    }
    m_ws.sendBinary(std::string(data.begin(), data.end()));
  }

  void onEvent(const std::string &event_name, EventHandler handler) {
    std::lock_guard<std::mutex> lock(m_eventMutex);
    m_eventHandlers[event_name].push_back(handler);
  }

  void pollEvents() {
    std::queue<QueuedEvent> events_to_dispatch;
    {
      std::lock_guard<std::mutex> lock(m_eventMutex);
      std::swap(events_to_dispatch, m_eventQueue);
    }

    while (!events_to_dispatch.empty()) {
      auto event = std::move(events_to_dispatch.front());
      events_to_dispatch.pop();

      std::vector<EventHandler> handlers;
      {
        std::lock_guard<std::mutex> lock(m_eventMutex);
        m_waitConsumedEventIds.erase(event.id);
        auto it = m_eventHandlers.find(event.name);
        if (it != m_eventHandlers.end()) {
          handlers = it->second;
        }
      }

      for (auto &handler : handlers) {
        try {
          handler(event.data);
        } catch (...) {
          // Ignore handler exceptions
        }
      }
    }
  }

  void setTimeout(std::chrono::seconds timeout) { m_timeout = timeout; }

private:
  void handleMessage(const ix::WebSocketMessagePtr &msg) {
    switch (msg->type) {
    case ix::WebSocketMessageType::Open:
      { std::lock_guard<std::mutex> lock(m_connectMutex); m_connected = true; }
      m_connectCv.notify_all();
      break;

    case ix::WebSocketMessageType::Close:
      m_connected = false;
      m_authEvent.notify_all();
      {
        std::lock_guard<std::mutex> lock(m_eventMutex);
        m_queryReplies.clear();
        m_eventQueue = {};
        m_waitConsumedEventIds.clear();
        for (auto &[name, waiters] : m_eventWaiters) for (auto &waiter : waiters) waiter.cv->notify_all();
      }
      // Notify all pending requests
      {
        std::lock_guard<std::mutex> lock(m_mutex);
        for (auto &[id, cv] : m_pending) {
          cv->notify_all();
        }
      }
      break;

    case ix::WebSocketMessageType::Error:
      { std::lock_guard<std::mutex> guard(m_connectMutex); m_connectError = msg->errorInfo.reason; }
      m_connectCv.notify_all();
      break;

    case ix::WebSocketMessageType::Message:
      if (!msg->binary) {
        handleTextMessage(msg->str);
      }
      break;

    default:
      break;
    }
  }

  void handleTextMessage(const std::string &message) {
    // std::cerr << "[DEBUG] Received: " << message << std::endl;
    try {
      json envelope = json::parse(message);
      std::string msg_type = envelope.value("type", "");

      if (msg_type == "resp") {
        std::string cmd_id = envelope.value("id", "");
        if (!cmd_id.empty()) {
          std::lock_guard<std::mutex> lock(m_mutex);
          // Only store response if someone is still waiting (prevents memory leak from late/timeout responses)
          auto it = m_pending.find(cmd_id);
          if (it != m_pending.end()) {
            m_responses[cmd_id] = envelope;
            it->second->notify_all();
          }
          // else: late response after timeout, discard to prevent leak
        }
      } else if (msg_type == "event") {
        std::string event_name = envelope.value("name", "");
        json data = envelope.value("data", json::object());
        if (!event_name.empty()) {
          std::unique_lock<std::mutex> lock(m_eventMutex);

          const bool queryResponse = data.is_object() && data.contains("request_id") &&
              (event_name == "camera_pose_response" || event_name == "pick_config_response" || event_name == "pick_info_response");
          bool delivered = false;
          // Check if anyone is waiting for this event
          if (m_eventWaiters.count(event_name) && !m_eventWaiters[event_name].empty()) {
            // Try to match with any waiter's filter
            for (auto &waiter : m_eventWaiters[event_name]) {
              if (!waiter.result->has_value() && waiter.filter(data)) {
                delivered = true;
                // Store result and notify this waiter
                *(waiter.result) = data;
                waiter.cv->notify_one();
                // Don't break - allow multiple waiters to receive the same event
              }
            }
          }

          // Query replies have a separate bounded inbox for the send/wait race.
          // Consumed replies never fill the regular subscription queue.
          if (queryResponse) {
            if (!delivered) {
              if (m_queryReplies.size() >= 4096) m_queryReplies.pop_front();
              m_queryReplies.push_back(QueuedEvent{0, event_name, data});
            }
            if (!m_eventHandlers.count(event_name) || m_eventHandlers[event_name].empty()) return;
          }
          if (m_eventQueue.size() >= 4096) {
            lock.unlock();
            m_ws.close();
            return;
          }
          m_eventQueue.push(QueuedEvent{m_nextQueuedEventId++, event_name, data});
        }
      } else if (msg_type == "auth_resp") {
        handleAuthResponse(envelope);
      }
    } catch (const json::exception &) {
      // Ignore malformed messages
    }
  }

  void authenticate() {
    std::optional<std::string> token_opt;
    if (const char* explicit_token = std::getenv("FRAMEVIZ_AUTH_TOKEN")) token_opt = explicit_token;
    else if (getWsUrlFromDiscovery() == std::optional<std::string>(m_url)) token_opt = getTokenFromDiscovery();
    if (!token_opt.has_value() || token_opt->empty()) {
      throw std::runtime_error("Authentication token required");
    }

    std::string token = *token_opt;
    // std::cerr << "[DEBUG] Authenticating with token from discovery file"
    //           << std::endl;

    m_authOk = false;
    m_authDone = false;

    json auth_msg = {{"type", "auth"}, {"token", token}};
    std::string msg_str = auth_msg.dump();
    { std::lock_guard<std::mutex> send_lock(m_sendMutex); m_ws.send(msg_str); }

    // Wait for auth response
    std::unique_lock<std::mutex> lock(m_mutex);
    bool auth_received = m_authEvent.wait_for(lock, m_timeout, [this] {
      return m_authDone || !m_connected;
    });

    if (!auth_received) {
      throw std::runtime_error("Authentication timeout");
    }

    if (!m_authOk) {
      throw std::runtime_error("Authentication failed: invalid token");
    }
    if (!m_authVersionOk) throw std::runtime_error(hostVersionError(m_hostVersion));
    m_authenticated = true;
    // std::cerr << "[DEBUG] Authentication successful" << std::endl;
  }

  void handleAuthResponse(const json &envelope) {
    {
      std::lock_guard<std::mutex> lock(m_mutex);
      m_authOk = envelope.value("ok", false);
      m_hostVersion = envelope.contains("protocol_version") && envelope["protocol_version"].is_string() ? envelope["protocol_version"].get<std::string>() : "";
      m_authVersionOk = isProtocolCompatible(m_hostVersion);
      m_authDone = true;
    }

    m_authEvent.notify_all();
  }

public:
  std::optional<json> waitForEvent(const std::string &event_name,
                                   std::chrono::seconds timeout) {
    // Default filter accepts all events
    return waitForEvent(event_name, [](const json &) { return true; }, timeout);
  }

  std::optional<json> waitForEvent(const std::string &event_name,
                                   std::function<bool(const json &)> filter,
                                   std::chrono::seconds timeout) {
    std::unique_lock<std::mutex> lock(m_eventMutex);

    // Create waiter
    EventWaiter waiter;
    waiter.cv = std::make_shared<std::condition_variable>();
    waiter.filter = filter;
    waiter.result = std::make_shared<std::optional<json>>();

    // Register waiter
    m_eventWaiters[event_name].push_back(waiter);

    for (auto it = m_queryReplies.begin(); it != m_queryReplies.end(); ++it) {
      if (it->name == event_name && filter(it->data)) {
        *waiter.result = it->data;
        m_queryReplies.erase(it);
        break;
      }
    }
    // Scan queued events without draining unrelated ones. This closes the race
    // where an event arrives while sendCommand() is still waiting for its
    // response, but before waitForEvent() registers the waiter.
    const size_t queued_count = m_eventQueue.size();
    for (size_t i = 0; i < queued_count; ++i) {
      auto queued = std::move(m_eventQueue.front());
      m_eventQueue.pop();

      if (!m_waitConsumedEventIds.count(queued.id)) {
        auto waiters_it = m_eventWaiters.find(queued.name);
        bool matched_any = false;
        if (waiters_it != m_eventWaiters.end()) {
          for (auto &existing_waiter : waiters_it->second) {
            if (!existing_waiter.result->has_value() &&
                existing_waiter.filter(queued.data)) {
              *(existing_waiter.result) = queued.data;
              existing_waiter.cv->notify_one();
              matched_any = true;
            }
          }
        }
        if (matched_any) {
          m_waitConsumedEventIds.insert(queued.id);
        }
      }

      m_eventQueue.push(std::move(queued));
    }

    if (waiter.result->has_value()) {
      auto &waiters = m_eventWaiters[event_name];
      waiters.erase(std::remove_if(waiters.begin(), waiters.end(),
        [&waiter](const EventWaiter& w) {
          return w.result.get() == waiter.result.get();
        }), waiters.end());
      if (waiters.empty()) {
        m_eventWaiters.erase(event_name);
      }
      return *(waiter.result);
    }

    // Wait for event or timeout
    bool received = waiter.cv->wait_for(lock, timeout, [&waiter, this]() {
      return waiter.result->has_value() || !m_connected;
    });

    // Cleanup - remove this waiter by identity (not by index, which is unsafe with concurrent waiters)
    auto &waiters = m_eventWaiters[event_name];
    waiters.erase(std::remove_if(waiters.begin(), waiters.end(),
      [&waiter](const EventWaiter& w) {
        // Compare by result pointer identity
        return w.result.get() == waiter.result.get();
      }), waiters.end());

    if (waiters.empty()) {
      m_eventWaiters.erase(event_name);
    }

    if (received && waiter.result->has_value()) {
      return *(waiter.result);
    }

    return std::nullopt;
  }

private:
  std::string m_url;
  ix::WebSocket m_ws;
  std::atomic<bool> m_connected;
  std::atomic<bool> m_authenticated;
  std::optional<std::string> m_connectError;

  std::mutex m_connectMutex;
  std::condition_variable m_connectCv;

  std::mutex m_mutex;
  std::mutex m_sendMutex;
  int m_requestId;
  std::unordered_map<std::string, std::shared_ptr<std::condition_variable>>
      m_pending;
  std::unordered_map<std::string, json> m_responses;
  std::chrono::seconds m_timeout;

  // Authentication
  std::condition_variable m_authEvent;
  std::atomic<bool> m_authOk;
  std::atomic<bool> m_authVersionOk{false};
  std::string m_hostVersion;
  std::atomic<bool> m_authDone{false};

  std::mutex m_eventMutex;
  std::unordered_map<std::string, std::vector<EventHandler>> m_eventHandlers;

  // Event waiting mechanism (support multiple concurrent waiters)
  struct EventWaiter {
    std::shared_ptr<std::condition_variable> cv;
    std::function<bool(const json &)> filter;
    std::shared_ptr<std::optional<json>> result;
  };
  struct QueuedEvent {
    size_t id;
    std::string name;
    json data;
  };
  std::unordered_map<std::string, std::vector<EventWaiter>> m_eventWaiters;
  std::queue<QueuedEvent> m_eventQueue;
  std::deque<QueuedEvent> m_queryReplies;
  std::unordered_set<size_t> m_waitConsumedEventIds;
  size_t m_nextQueuedEventId = 1;
};

// FrameVizClient implementation (delegate to Impl)

FrameVizClient::FrameVizClient(const std::string &url)
    : m_impl(std::make_unique<Impl>(url)) {}

FrameVizClient::~FrameVizClient() = default;

FrameVizClient::FrameVizClient(FrameVizClient &&) noexcept = default;
FrameVizClient &FrameVizClient::operator=(FrameVizClient &&) noexcept = default;

void FrameVizClient::connect(std::chrono::seconds timeout) {
  m_impl->connect(timeout);
}

void FrameVizClient::close() { m_impl->close(); }

bool FrameVizClient::isConnected() const { return m_impl->isConnected(); }

json FrameVizClient::sendCommand(const std::string &name, const json &args) {
  return m_impl->sendCommand(name, args);
}

int FrameVizClient::presentView(const std::string &browser_session,
                               const std::string &view_id) {
  return sendCommand("present_view", {{"browser_session", browser_session},
                                     {"view_id", view_id}}).at("viewer_count").get<int>();
}

json FrameVizClient::sendCommandWithBinary(
    const std::string &name, const json &args,
    const std::vector<uint8_t> &binary_data) {
  return m_impl->sendCommandWithBinary(name, args, binary_data);
}

void FrameVizClient::sendBinary(const std::vector<uint8_t> &data) {
  m_impl->sendBinary(data);
}

void FrameVizClient::onEvent(const std::string &event_name,
                             EventHandler handler) {
  m_impl->onEvent(event_name, handler);
}

void FrameVizClient::pollEvents() { m_impl->pollEvents(); }

void FrameVizClient::setTimeout(std::chrono::seconds timeout) {
  m_impl->setTimeout(timeout);
}

std::optional<json> FrameVizClient::waitForEvent(const std::string &event_name,
                                           std::chrono::seconds timeout) {
  return m_impl->waitForEvent(event_name, timeout);
}

std::optional<json> FrameVizClient::waitForEvent(const std::string &event_name,
                                           std::function<bool(const json &)> filter,
                                           std::chrono::seconds timeout) {
  return m_impl->waitForEvent(event_name, filter, timeout);
}

} // namespace frameviz
