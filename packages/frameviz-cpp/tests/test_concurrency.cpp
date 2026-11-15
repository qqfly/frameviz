/**
 * @file test_concurrency.cpp
 * @brief Concurrency and error handling tests for FrameViz C++ SDK
 *
 * Maintainer: qqfly
 * @date 2026-01-26
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#include <frameviz/client.hpp>
#include <frameviz/viz.hpp>
#include <frameviz/discovery.hpp>
#include <frameviz/tauri.hpp>
#include "test_utils.hpp"
#include <gtest/gtest.h>
#include <cstdlib>
#include <memory>
#include <thread>
#include <vector>
#include <atomic>
#include <chrono>

namespace frameviz {

namespace {

bool ShouldRunPerfTests() {
  return std::getenv("FRAMEVIZ_RUN_PERF") != nullptr;
}

}  // namespace

// ─────────────────────────────────────────────────────────────────────────────
// Concurrency Tests (require running Host)
// ─────────────────────────────────────────────────────────────────────────────

TEST(ConcurrencyTest, DISABLED_MultiThreadedWaitForEvent) {
  // Use client directly so we can register waiters before triggering the event.
  FrameVizClient client(testutil::resolveTestWsUrl());
  client.connect(std::chrono::seconds(5));

  json scene_result = client.sendCommand("create_scene", {});
  std::string scene_id = scene_result["scene_id"];
  json view_result = client.sendCommand("create_view", {{"scene_id", scene_id}});
  std::string view_id = view_result["view_id"];

  std::atomic<int> success_count{0};
  std::vector<std::thread> threads;

  // Launch 5 threads, each waiting for viewer_ready event (this view)
  for (int i = 0; i < 5; i++) {
    threads.emplace_back([&client, &success_count, &view_id]() {
      auto event = client.waitForEvent(
          "viewer_ready",
          [&](const json &data) {
            return data.contains("view_id") && data["view_id"] == view_id;
          },
          std::chrono::seconds(15));
      if (event.has_value()) {
        success_count++;
      }
    });
  }

  // Give threads time to start waiting
  std::this_thread::sleep_for(std::chrono::milliseconds(100));

  // Trigger viewer_ready by opening the view in Tauri
  if (!tryOpenTauriWindow(view_id, "FrameViz Test", 900, 700,
                          std::nullopt, std::nullopt, "", scene_id)) {
    client.close(); // release waiters
    for (auto &t : threads) {
      t.join();
    }
    GTEST_SKIP() << "Tauri control server not available; viewer not started.";
  }

  // Wait for all threads
  for (auto &t : threads) {
    t.join();
  }

  // At least one thread should have received the event
  EXPECT_GE(success_count.load(), 1);

  client.close();
}

TEST(ConcurrencyTest, DISABLED_MultiThreadedWaitForEventWithFilter) {
  auto viz = Viz::open();

  std::atomic<int> thread1_success{0};
  std::atomic<int> thread2_success{0};

  // Thread 1: Wait for pick event with object_handle == "box1"
  std::thread t1([&viz, &thread1_success]() {
    auto event = viz->waitForEvent("pick", [](const json &data) {
      return data.contains("object_handle") && data["object_handle"] == "box1";
    }, std::chrono::seconds(10));

    if (event.has_value()) {
      thread1_success++;
    }
  });

  // Thread 2: Wait for pick event with object_handle == "box2"
  std::thread t2([&viz, &thread2_success]() {
    auto event = viz->waitForEvent("pick", [](const json &data) {
      return data.contains("object_handle") && data["object_handle"] == "box2";
    }, std::chrono::seconds(10));

    if (event.has_value()) {
      thread2_success++;
    }
  });

  // Simulate pick events (would normally come from user interaction)
  // This test verifies that filters work correctly in multi-threaded context

  t1.join();
  t2.join();

  // Note: Without actual user interaction, events won't be triggered
  // This test mainly verifies thread safety

  viz->close();
}

TEST(ConcurrencyTest, DISABLED_ParallelObjectCreation) {
  auto viz = Viz::open();

  std::vector<std::thread> threads;
  std::vector<Handle> handles(10);

  // Create 10 boxes in parallel
  for (int i = 0; i < 10; i++) {
    threads.emplace_back([&viz, &handles, i]() {
      handles[i] = viz->addBox(
        {1, 1, 1},
        {static_cast<float>(i) * 2.0f, 0, 0},
        {0, 0, 0, 1},
        {static_cast<float>(i) / 10.0f, 0, 0}
      );
    });
  }

  for (auto &t : threads) {
    t.join();
  }

  // Verify all handles are valid and unique
  for (size_t i = 0; i < handles.size(); i++) {
    EXPECT_FALSE(handles[i].empty());
    EXPECT_TRUE(viz->isObjectAlive(handles[i]));

    // Check uniqueness
    for (size_t j = i + 1; j < handles.size(); j++) {
      EXPECT_NE(handles[i], handles[j]);
    }
  }

  viz->close();
}

TEST(ConcurrencyTest, DISABLED_ParallelTransformUpdates) {
  auto viz = Viz::open();

  // Create 100 boxes
  std::vector<Handle> handles;
  for (int i = 0; i < 100; i++) {
    handles.push_back(viz->addBox());
  }

  std::atomic<int> update_count{0};
  std::vector<std::thread> threads;

  // Update transforms in parallel (10 threads, 10 boxes each)
  for (int tid = 0; tid < 10; tid++) {
    threads.emplace_back([&viz, &handles, &update_count, tid]() {
      for (int i = 0; i < 10; i++) {
        int idx = tid * 10 + i;
        viz->setTransform(handles[idx],
                          {static_cast<float>(idx) * 0.5f, 0, 0},
                          {0, 0, 0, 1});
        update_count++;
      }
    });
  }

  for (auto &t : threads) {
    t.join();
  }

  EXPECT_EQ(update_count.load(), 100);

  viz->close();
}

// ─────────────────────────────────────────────────────────────────────────────
// Chunk Group Tests (require running Host)
// ─────────────────────────────────────────────────────────────────────────────

TEST(ChunkGroupTest, DISABLED_ChunkedPointsGroupHandleOperations) {
  std::unique_ptr<Viz> viz;
  try {
    viz = Viz::open();
  } catch (const std::exception &e) {
    GTEST_SKIP() << "Host not available: " << e.what();
  }

  const size_t count = 500001; // > 500k to trigger chunking
  std::vector<float> positions(count * 3);
  for (size_t i = 0; i < count; i++) {
    const size_t base = i * 3;
    positions[base] = static_cast<float>(i % 1000) * 0.01f;
    positions[base + 1] = static_cast<float>((i / 1000) % 1000) * 0.01f;
    positions[base + 2] = 0.0f;
  }

  Handle handle = viz->addPoints(positions, Color{0.2f, 0.6f, 0.9f}, 2.0f);
  ASSERT_FALSE(handle.empty());
  EXPECT_NE(handle.rfind("chunk_group_", 0), 0u);
  EXPECT_TRUE(viz->isObjectAlive(handle));

  viz->setTransform(handle, {1.0f, 2.0f, 3.0f}, {0.0f, 0.0f, 0.0f, 1.0f});
  Pose pose = viz->getTransform(handle);
  EXPECT_FLOAT_EQ(pose.pos[0], 1.0f);
  EXPECT_FLOAT_EQ(pose.pos[1], 2.0f);
  EXPECT_FLOAT_EQ(pose.pos[2], 3.0f);

  viz->setColor(handle, {0.1f, 0.2f, 0.3f, 1.0f});
  viz->setVisible(handle, false);

  viz->removeObject(handle);
  EXPECT_FALSE(viz->isObjectAlive(handle));

  viz->close();
}

// ─────────────────────────────────────────────────────────────────────────────
// Error Handling Tests
// ─────────────────────────────────────────────────────────────────────────────

TEST(ErrorHandlingTest, ConnectionTimeout) {
  // Try to connect to non-existent host
  FrameVizClient client("ws://127.0.0.1:99999");

  EXPECT_THROW({
    client.connect(std::chrono::seconds(1)); // 1 second timeout
  }, std::runtime_error);

  EXPECT_FALSE(client.isConnected());
}

TEST(ErrorHandlingTest, DISABLED_CommandOnClosedConnection) {
  FrameVizClient client(testutil::resolveTestWsUrl());
  client.connect(std::chrono::seconds(5));
  client.close();

  EXPECT_THROW({
    client.sendCommand("create_scene", {});
  }, std::runtime_error);
}

TEST(ErrorHandlingTest, DISABLED_InvalidCommandArgs) {
  auto viz = Viz::open();

  // Try to set transform on non-existent object
  EXPECT_THROW({
    viz->setTransform("nonexistent_handle", {0, 0, 0}, {0, 0, 0, 1});
  }, std::runtime_error);

  viz->close();
}

TEST(ErrorHandlingTest, DISABLED_RemoveNonExistentObject) {
  auto viz = Viz::open();

  // Remove non-existent object (should not throw, but isObjectAlive should return false)
  viz->removeObject("nonexistent_handle");

  EXPECT_FALSE(viz->isObjectAlive("nonexistent_handle"));

  viz->close();
}

TEST(ErrorHandlingTest, DISABLED_DoubleRemove) {
  auto viz = Viz::open();

  Handle box = viz->addBox();
  EXPECT_TRUE(viz->isObjectAlive(box));

  viz->removeObject(box);
  EXPECT_FALSE(viz->isObjectAlive(box));

  // Remove again (should be safe)
  viz->removeObject(box);
  EXPECT_FALSE(viz->isObjectAlive(box));

  viz->close();
}

// ─────────────────────────────────────────────────────────────────────────────
// Edge Case Tests (require running Host)
// ─────────────────────────────────────────────────────────────────────────────

TEST(EdgeCaseTest, DISABLED_EmptyPositionsArray) {
  auto viz = Viz::open();

  std::vector<float> empty_positions;

  // Adding points with empty array should handle gracefully
  EXPECT_NO_THROW({
    auto handle = viz->addPoints(empty_positions);
    if (!handle.empty()) {
      EXPECT_TRUE(viz->isObjectAlive(handle));
    }
  });

  viz->close();
}

TEST(EdgeCaseTest, DISABLED_MismatchedArraySizes) {
  auto viz = Viz::open();

  std::vector<float> positions = {0, 0, 0, 1, 1, 1}; // 2 points
  std::vector<Color> colors = {{1.0f, 0.0f, 0.0f}}; // Only 1 color

  // Mismatched sizes should be handled
  EXPECT_THROW({
    viz->addPoints(positions, colors);
  }, std::runtime_error);

  viz->close();
}

TEST(EdgeCaseTest, DISABLED_VeryLargeInstances) {
  auto viz = Viz::open();

  // Create 50,000 instances
  const size_t count = 50000;
  std::vector<float> positions(count * 3);

  for (size_t i = 0; i < count * 3; i++) {
    positions[i] = (rand() / (float)RAND_MAX - 0.5f) * 100.0f;
  }

  Handle instances = viz->addInstances(
    InstanceType::BOX,
    positions,
    {},
    {},
    {},
    Color{0.5f, 0.5f, 0.5f},
    0.5f,
    Vec3{0.1f, 0.1f, 0.1f}
  );

  EXPECT_TRUE(viz->isObjectAlive(instances));

  viz->close();
}

TEST(EdgeCaseTest, DISABLED_RapidCreateDestroy) {
  auto viz = Viz::open();

  // Rapidly create and destroy 1000 objects
  for (int i = 0; i < 1000; i++) {
    Handle box = viz->addBox();
    EXPECT_TRUE(viz->isObjectAlive(box));
    viz->removeObject(box);
    EXPECT_FALSE(viz->isObjectAlive(box));
  }

  viz->close();
}

TEST(EdgeCaseTest, DISABLED_ExtremeCameraPositions) {
  auto viz = Viz::open();

  if (!viz->waitForViewer(std::chrono::seconds(15))) {
    GTEST_SKIP() << "Viewer not ready; skipping extreme camera positions test.";
  }

  // Very far camera
  viz->setCameraPose({1000, 1000, 1000}, {0, 0, 0}, {0, 0, 1});

  CameraPose cam = viz->getCameraPose();
  EXPECT_FLOAT_EQ(cam.eye[0], 1000.0f);

  // Very close camera
  viz->setCameraPose({0.001f, 0.001f, 0.001f}, {0, 0, 0}, {0, 0, 1});

  cam = viz->getCameraPose();
  EXPECT_FLOAT_EQ(cam.eye[0], 0.001f);

  viz->close();
}

TEST(EdgeCaseTest, DISABLED_ZeroSizeBox) {
  auto viz = Viz::open();

  // Box with zero size (should handle gracefully or reject)
  EXPECT_NO_THROW({
    Handle box = viz->addBox({0, 0, 0});
  });

  viz->close();
}

TEST(EdgeCaseTest, DISABLED_NegativeSizes) {
  auto viz = Viz::open();

  // Negative sizes should be handled (either abs() or error)
  EXPECT_NO_THROW({
    Handle box = viz->addBox({-1, -1, -1});
  });

  viz->close();
}

// ─────────────────────────────────────────────────────────────────────────────
// Performance Tests
// ─────────────────────────────────────────────────────────────────────────────

TEST(PerformanceTest, BatchTransformPerformance) {
  if (!ShouldRunPerfTests()) {
    GTEST_SKIP() << "Set FRAMEVIZ_RUN_PERF=1 to run performance tests.";
  }
  auto viz = Viz::open();

  // Create 1000 objects
  std::vector<Handle> handles;
  for (int i = 0; i < 1000; i++) {
    handles.push_back(viz->addCylinder(0.02f, 0.5f));
  }

  // Prepare batch transforms
  std::vector<TransformItem> items;
  for (int i = 0; i < 1000; i++) {
    Pose pose{{static_cast<float>(i) * 0.1f, 0, 0}, {0, 0, 0, 1}, {1, 1, 1}};
    items.push_back({handles[i], pose});
  }

  // Measure batch update time
  auto start = std::chrono::high_resolution_clock::now();
  viz->setObjectTransforms(items);
  auto end = std::chrono::high_resolution_clock::now();

  auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
  std::cout << "Batch transform (1000 objects): " << duration.count() << "ms" << std::endl;

  // Should complete in reasonable time (< 100ms)
  EXPECT_LT(duration.count(), 100);

  viz->close();
}

TEST(PerformanceTest, InstanceUpdatePerformance) {
  if (!ShouldRunPerfTests()) {
    GTEST_SKIP() << "Set FRAMEVIZ_RUN_PERF=1 to run performance tests.";
  }
  auto viz = Viz::open();

  // Create 10,000 instances
  const size_t count = 10000;
  std::vector<float> positions(count * 3);

  for (size_t i = 0; i < count * 3; i++) {
    positions[i] = (rand() / (float)RAND_MAX - 0.5f) * 50.0f;
  }

  Handle instances = viz->addInstances(
    InstanceType::SPHERE,
    positions,
    {},
    {},
    {},
    Color{1.0f, 0.0f, 0.0f},
    1.0f,
    std::nullopt
  );

  // Update positions 10 times and measure average time
  auto total_duration = std::chrono::milliseconds(0);

  for (int iter = 0; iter < 10; iter++) {
    for (size_t i = 0; i < count * 3; i++) {
      positions[i] += (rand() / (float)RAND_MAX - 0.5f) * 0.1f;
    }

    auto start = std::chrono::high_resolution_clock::now();
    viz->updateInstances(instances, positions);
    auto end = std::chrono::high_resolution_clock::now();

    total_duration += std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
  }

  auto avg_duration = total_duration.count() / 10;
  std::cout << "Instance update (10,000 instances, avg): " << avg_duration << "ms" << std::endl;

  // Should complete in reasonable time (< 50ms per update)
  EXPECT_LT(avg_duration, 50);

  viz->close();
}

} // namespace frameviz
