/**
 * @file client.hpp
 * @brief Low-level WebSocket client for FrameViz protocol
 *
 * Maintainer: qqfly
 * @date 2026-01-25
 * @bug No known bugs
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#ifndef FRAMEVIZ_CPP_CLIENT_HPP
#define FRAMEVIZ_CPP_CLIENT_HPP

#include <chrono>
#include <condition_variable>
#include <functional>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <unordered_map>

#include <nlohmann/json.hpp>

#include "types.hpp"

namespace frameviz {

using json = nlohmann::json;
using EventHandler = std::function<void(const json &)>;

/**
 * @brief Low-level WebSocket client for FrameViz Host communication.
 *
 * Provides synchronous blocking API for sending commands and receiving
 * responses. Events are queued and can be polled.
 */
class FrameVizClient {
public:
  /**
   * @brief Construct a new client instance.
   * @param url WebSocket URL (default: ws://127.0.0.1:9527)
   */
  explicit FrameVizClient(const std::string &url = "ws://127.0.0.1:9527");

  /**
   * @brief Destructor. Closes connection if open.
   */
  ~FrameVizClient();

  // Non-copyable
  FrameVizClient(const FrameVizClient &) = delete;
  FrameVizClient &operator=(const FrameVizClient &) = delete;

  // Movable
  FrameVizClient(FrameVizClient &&) noexcept;
  FrameVizClient &operator=(FrameVizClient &&) noexcept;

  /**
   * @brief Connect to the Host (blocking).
   * @param timeout Connection timeout duration
   * @throws std::runtime_error on connection failure
   */
  void connect(std::chrono::seconds timeout = std::chrono::seconds(10));

  /**
   * @brief Close the connection.
   */
  void close();

  /**
   * @brief Check if connected.
   */
  bool isConnected() const;

  /**
   * @brief Send a command and wait for response (blocking).
   * @param name Command name
   * @param args Command arguments
   * @return Response result as JSON
   * @throws std::runtime_error on error or timeout
   */
  json sendCommand(const std::string &name, const json &args = json::object());

  /**
   * @brief Send a command with binary data and wait for response.
   * @param name Command name
   * @param args Command arguments
   * @param binary_data Binary payload
   * @return Response result as JSON
   */
  json sendCommandWithBinary(const std::string &name, const json &args,
                             const std::vector<uint8_t> &binary_data);

  /**
   * @brief Send raw binary frame.
   * @param data Binary data
   */
  void sendBinary(const std::vector<uint8_t> &data);

  /**
   * @brief Register event handler.
   * @param event_name Event name to handle
   * @param handler Callback function
   */
  void onEvent(const std::string &event_name, EventHandler handler);

  /**
   * @brief Poll and dispatch queued events.
   */
  void pollEvents();

  /**
   * @brief Wait for a specific event to arrive.
   * @param event_name The event name to wait for
   * @param timeout Timeout duration
   * @return Event data if received, std::nullopt if timeout
   */
  std::optional<json> waitForEvent(const std::string &event_name,
                                  std::chrono::seconds timeout = std::chrono::seconds(2));

  /**
   * @brief Wait for a specific event with custom filter.
   * @param event_name The event name to wait for
   * @param filter Predicate function to filter event data
   * @param timeout Timeout duration
   * @return Event data if received, std::nullopt if timeout
   */
  std::optional<json> waitForEvent(const std::string &event_name,
                                  std::function<bool(const json &)> filter,
                                  std::chrono::seconds timeout = std::chrono::seconds(2));

  /**
   * @brief Set command timeout.
   * @param timeout Timeout duration
   */
  void setTimeout(std::chrono::seconds timeout);

private:
  class Impl;
  std::unique_ptr<Impl> m_impl;
};

} // namespace frameviz

#endif // FRAMEVIZ_CPP_CLIENT_HPP
