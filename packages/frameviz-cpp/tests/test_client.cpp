/**
 * @file test_client.cpp
 * @brief Basic tests for FrameViz C++ SDK
 *
 * Maintainer: qqfly
 * @date 2026-01-25
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#include <frameviz/client.hpp>
#include <frameviz/protocol_version.hpp>
#include <frameviz/types.hpp>
#include <frameviz/viz.hpp>
#include <frameviz/internal/color_utils.hpp>
#include <frameviz/internal/ws_url.hpp>
#include <frameviz/discovery.hpp>
#include <frameviz/tauri.hpp>
#include "test_utils.hpp"
#include <gtest/gtest.h>
#include <nlohmann/json.hpp>
#include <thread>
#include <chrono>
#include <cstdlib>
#include <unistd.h>
#include <fstream>

namespace frameviz
{

using json = nlohmann::json;
using namespace std::chrono_literals;

TEST(VersionTest, SameSeriesAcceptsPatchesAndRejectsMalformedValues) {
    for (const auto* version : {"0.5.0", "0.5.1", "0.5.999999999"}) EXPECT_TRUE(isProtocolCompatible(version));
    for (const auto* version : {"0.4.9", "0.6.0", "0.5", "00.5.1", "0.5.01", "0.5.1-beta", "0.5.9999999999"}) EXPECT_FALSE(isProtocolCompatible(version));
}

TEST(VersionTest, UpgradeDirectionIdentifiesTheOlderSide) {
    EXPECT_NE(hostVersionError("0.4.9").find("Upgrade the FrameViz runtime"), std::string::npos);
    EXPECT_NE(hostVersionError("0.6.0").find("Upgrade the C++ SDK"), std::string::npos);
    EXPECT_NE(hostVersionError("").find("malformed"), std::string::npos);
}

class ScopedEnvVar {
public:
    explicit ScopedEnvVar(const std::string& name, const std::string& value)
        : name_(name)
    {
        const char* old = std::getenv(name_.c_str());
        if (old != nullptr) {
            had_old_ = true;
            old_value_ = old;
        }
        setenv(name_.c_str(), value.c_str(), 1);
    }

    explicit ScopedEnvVar(const std::string& name)
        : name_(name)
    {
        const char* old = std::getenv(name_.c_str());
        if (old != nullptr) {
            had_old_ = true;
            old_value_ = old;
        }
        unsetenv(name_.c_str());
    }

    ~ScopedEnvVar() {
        if (had_old_) {
            setenv(name_.c_str(), old_value_.c_str(), 1);
        } else {
            unsetenv(name_.c_str());
        }
    }

    ScopedEnvVar(const ScopedEnvVar&) = delete;
    ScopedEnvVar& operator=(const ScopedEnvVar&) = delete;

private:
    std::string name_;
    bool had_old_ = false;
    std::string old_value_;
};

// ─────────────────────────────────────────────────────────────────────────────
// Type Tests
// ─────────────────────────────────────────────────────────────────────────────

TEST(TypesTest, Vec3Default)
{
    Vec3 v = {0, 0, 0};
    EXPECT_FLOAT_EQ(v[0], 0.0f);
    EXPECT_FLOAT_EQ(v[1], 0.0f);
    EXPECT_FLOAT_EQ(v[2], 0.0f);
}

TEST(TypesTest, QuatIdentity)
{
    Quat q = {0, 0, 0, 1};
    EXPECT_FLOAT_EQ(q[3], 1.0f); // w component
}

TEST(TypesTest, PoseDefaults)
{
    Pose p;
    EXPECT_FLOAT_EQ(p.pos[0], 0.0f);
    EXPECT_FLOAT_EQ(p.quat[3], 1.0f);
    EXPECT_FLOAT_EQ(p.scale[0], 1.0f);
}

TEST(TypesTest, BufferRefInit)
{
    BufferRef ref{"buf_123", "f32", {100, 3}};
    EXPECT_EQ(ref.buffer_id, "buf_123");
    EXPECT_EQ(ref.dtype, "f32");
    EXPECT_EQ(ref.shape[0], 100);
    EXPECT_EQ(ref.shape[1], 3);
}

TEST(TypesTest, CameraPoseDefaults)
{
    CameraPose cam;
    EXPECT_FLOAT_EQ(cam.eye[0], 5.0f);
    EXPECT_FLOAT_EQ(cam.eye[1], 5.0f);
    EXPECT_FLOAT_EQ(cam.eye[2], 5.0f);
    EXPECT_FLOAT_EQ(cam.target[0], 0.0f);
    EXPECT_FLOAT_EQ(cam.target[1], 0.0f);
    EXPECT_FLOAT_EQ(cam.target[2], 0.0f);
    EXPECT_FLOAT_EQ(cam.up[0], 0.0f);
    EXPECT_FLOAT_EQ(cam.up[1], 0.0f);
    EXPECT_FLOAT_EQ(cam.up[2], 1.0f);
}

TEST(TypesTest, TransformItemInit)
{
    Pose pose{{1, 2, 3}, {0.0f, 0.0f, 0.707f, 0.707f}, {2, 2, 2}};
    TransformItem item{"obj_1", pose};
    EXPECT_EQ(item.handle, "obj_1");
    EXPECT_FLOAT_EQ(item.pose.pos[0], 1.0f);
    EXPECT_FLOAT_EQ(item.pose.quat[2], 0.707f);
    EXPECT_FLOAT_EQ(item.pose.scale[0], 2.0f);
}

TEST(TypesTest, ColorRGB)
{
    Color rgb = {1.0f, 0.5f, 0.0f};
    EXPECT_EQ(rgb.size(), 3);
    EXPECT_FLOAT_EQ(rgb[0], 1.0f);
    EXPECT_FLOAT_EQ(rgb[1], 0.5f);
    EXPECT_FLOAT_EQ(rgb[2], 0.0f);
}

TEST(TypesTest, ColorRGBA)
{
    Color rgba = {1.0f, 0.5f, 0.0f, 0.8f};
    EXPECT_EQ(rgba.size(), 4);
    EXPECT_FLOAT_EQ(rgba[3], 0.8f); // alpha
}

TEST(ColorUtilsTest, PackColorsToU8)
{
    std::vector<Color> colors = {
        {0.0f, 0.5f, 1.0f},
        {1.0f, 1.0f, 1.0f},
    };
    auto packed = detail::packColorsToU8(colors, "test", colors.size());
    ASSERT_EQ(packed.size(), 6u);
    EXPECT_EQ(packed[0], 0u);
    EXPECT_EQ(packed[1], 128u);
    EXPECT_EQ(packed[2], 255u);
    EXPECT_EQ(packed[3], 255u);
    EXPECT_EQ(packed[4], 255u);
    EXPECT_EQ(packed[5], 255u);

    std::vector<Color> bad = {{1.2f, 0.0f, 0.0f}};
    EXPECT_THROW(detail::packColorsToU8(bad, "bad"), std::runtime_error);
    EXPECT_THROW(detail::packColorsToU8(colors, "mismatch", colors.size() + 1),
                 std::runtime_error);
}

TEST(TypesTest, ProtocolConstants)
{
    // Verify format (x.y.z) rather than exact value
    std::string ver(PROTOCOL_VERSION);
    EXPECT_FALSE(ver.empty());
    EXPECT_EQ(std::count(ver.begin(), ver.end(), '.'), 2);

    std::string minVer(MIN_COMPATIBLE_VERSION);
    EXPECT_FALSE(minVer.empty());
    EXPECT_EQ(std::count(minVer.begin(), minVer.end(), '.'), 2);

    EXPECT_EQ(DEFAULT_WS_PORT, 9527);
}

// ─────────────────────────────────────────────────────────────────────────────
// Enum Tests
// ─────────────────────────────────────────────────────────────────────────────

TEST(EnumTest, InstanceType)
{
    InstanceType box = InstanceType::BOX;
    InstanceType sphere = InstanceType::SPHERE;
    InstanceType axes = InstanceType::AXES;

    EXPECT_NE(box, sphere);
    EXPECT_NE(sphere, axes);
}

TEST(EnumTest, FacesFormat)
{
    FacesFormat tri = FacesFormat::TRI;
    FacesFormat poly = FacesFormat::POLY;

    EXPECT_NE(tri, poly);
}

TEST(EnumTest, ErrorCode)
{
    ErrorCode ok = ErrorCode::OK;
    ErrorCode conn_failed = ErrorCode::CONNECTION_FAILED;
    ErrorCode timeout = ErrorCode::CONNECTION_TIMEOUT;

    EXPECT_EQ(static_cast<int>(ok), 0);
    EXPECT_NE(ok, conn_failed);
    EXPECT_NE(conn_failed, timeout);
}

// ─────────────────────────────────────────────────────────────────────────────
// Discovery Tests
// ─────────────────────────────────────────────────────────────────────────────

TEST(DiscoveryTest, GetDiscoveryPath)
{
    // Test default path (no env var)
    auto path = getDiscoveryPath();
    EXPECT_TRUE(path.has_value());

    if (path) {
        // Path belongs to the independent project namespace
        EXPECT_NE(path->find("qqfly"), std::string::npos);
        EXPECT_NE(path->find("frameviz"), std::string::npos);
    }
}

TEST(DiscoveryTest, DiscoveryInfoInit)
{
    DiscoveryInfo info;
    info.ws_url = "ws://127.0.0.1:9527";
    info.viewer_url = "http://127.0.0.1:8080/";
    info.token = "test_token_123";
    info.port = 9527;
    info.version = "0.3.3";

    EXPECT_EQ(info.ws_url, "ws://127.0.0.1:9527");
    EXPECT_EQ(info.viewer_url, "http://127.0.0.1:8080/");
    EXPECT_EQ(info.token, "test_token_123");
    EXPECT_EQ(info.port, 9527);
    EXPECT_EQ(info.version, "0.3.3");
}

TEST(DiscoveryTest, ResolveWsUrlFallbackWhenDiscoveryMissing)
{
    char path[] = "/tmp/frameviz_discovery_XXXXXX";
    int fd = mkstemp(path);
    if (fd >= 0) {
        close(fd);
        unlink(path);
    }
    ScopedEnvVar discovery_path("FRAMEVIZ_DISCOVERY_PATH", path);

    EXPECT_EQ(resolveWsUrl("ws://127.0.0.1:9527"), "ws://127.0.0.1:9527");
    EXPECT_EQ(resolveWsUrl("wss://127.0.0.1:9527"), "wss://127.0.0.1:9527");
    EXPECT_EQ(resolveWsUrl("ws://127.0.0.1:9527/"), "ws://127.0.0.1:9527/");
    EXPECT_EQ(resolveWsUrl("WS://LOCALHOST:9527"), "WS://LOCALHOST:9527");

}

TEST(DiscoveryTest, ResolveWsUrlUsesDiscoveryWhenAvailable)
{
    char path[] = "/tmp/frameviz_discovery_XXXXXX";
    int fd = mkstemp(path);
    if (fd >= 0) {
        close(fd);
    }
    std::ofstream file(path);
    file << R"({"ws_url":"ws://10.0.0.1:1234","version":"0.5.7"})";
    file.close();

    ScopedEnvVar discovery_path("FRAMEVIZ_DISCOVERY_PATH", path);

    EXPECT_EQ(resolveWsUrl("ws://127.0.0.1:9527"), "ws://10.0.0.1:1234");
    EXPECT_EQ(resolveWsUrl("wss://127.0.0.1:9527"), "ws://10.0.0.1:1234");
    EXPECT_EQ(resolveWsUrl("ws://127.0.0.1:9527/path"), "ws://10.0.0.1:1234");
    EXPECT_EQ(resolveWsUrl("ws://127.0.0.2:9527"), "ws://127.0.0.2:9527");

    unlink(path);
}

TEST(DiscoveryTest, GetPortFromDiscoveryReturnsNulloptWhenMissing)
{
    char path[] = "/tmp/frameviz_discovery_XXXXXX";
    int fd = mkstemp(path);
    if (fd >= 0) {
        close(fd);
    }
    std::ofstream file(path);
    file << R"({"ws_url":"ws://10.0.0.1:1234"})";
    file.close();

    ScopedEnvVar discovery_path("FRAMEVIZ_DISCOVERY_PATH", path);

    auto port = getPortFromDiscovery();
    EXPECT_FALSE(port.has_value());

    unlink(path);
}

TEST(DiscoveryTest, GetViewerUrlFromDiscovery)
{
    char path[] = "/tmp/frameviz_discovery_XXXXXX";
    int fd = mkstemp(path);
    if (fd >= 0) {
        close(fd);
    }
    std::ofstream file(path);
    file << R"({"viewer_url":"http://127.0.0.1:8080/"})";
    file.close();

    ScopedEnvVar discovery_path("FRAMEVIZ_DISCOVERY_PATH", path);
    auto viewer_url = getViewerUrlFromDiscovery();
    ASSERT_TRUE(viewer_url.has_value());
    EXPECT_EQ(*viewer_url, "http://127.0.0.1:8080/");

    unlink(path);
}

// ─────────────────────────────────────────────────────────────────────────────
// Tauri Tests
// ─────────────────────────────────────────────────────────────────────────────

TEST(TauriTest, GetTauriControlPortDefault)
{
    ScopedEnvVar tauri_port("FRAMEVIZ_TAURI_CONTROL_PORT");
    int port = getTauriControlPort();
    EXPECT_EQ(port, 9528); // default
}

TEST(TauriTest, GetTauriControlPortEnv)
{
    ScopedEnvVar tauri_port("FRAMEVIZ_TAURI_CONTROL_PORT", "12345");
    int port = getTauriControlPort();
    EXPECT_EQ(port, 12345);
}

TEST(TauriTest, GetTauriControlPortInvalidEnv)
{
    ScopedEnvVar tauri_port("FRAMEVIZ_TAURI_CONTROL_PORT", "invalid");
    int port = getTauriControlPort();
    EXPECT_EQ(port, 9528); // fallback to default
}

// ─────────────────────────────────────────────────────────────────────────────
// JSON Serialization Tests
// ─────────────────────────────────────────────────────────────────────────────

TEST(JSONTest, Vec3Serialization)
{
    Vec3 v = {1.5f, 2.5f, 3.5f};
    json j = v;

    EXPECT_EQ(j.size(), 3);
    EXPECT_EQ(j[0], 1.5);
    EXPECT_EQ(j[1], 2.5);
    EXPECT_EQ(j[2], 3.5);
}

TEST(JSONTest, QuatSerialization)
{
    Quat q = {0.0f, 0.0f, 0.707f, 0.707f};
    json j = q;

    EXPECT_EQ(j.size(), 4);
    EXPECT_NEAR(j[2], 0.707, 1e-5);
    EXPECT_NEAR(j[3], 0.707, 1e-5);
}

TEST(JSONTest, PoseSerialization)
{
    Pose pose{{1, 2, 3}, {0, 0, 0, 1}, {2, 2, 2}};
    json j = {{"pos", pose.pos}, {"quat", pose.quat}, {"scale", pose.scale}};

    EXPECT_EQ(j["pos"][0], 1);
    EXPECT_EQ(j["quat"][3], 1);
    EXPECT_EQ(j["scale"][0], 2);
}

TEST(JSONTest, BufferRefSerialization)
{
    BufferRef ref{"buf_001", "f32", {1000, 3}};
    json j = {{"buffer_id", ref.buffer_id},
              {"dtype", ref.dtype},
              {"shape", ref.shape}};

    EXPECT_EQ(j["buffer_id"], "buf_001");
    EXPECT_EQ(j["dtype"], "f32");
    EXPECT_EQ(j["shape"][0], 1000);
    EXPECT_EQ(j["shape"][1], 3);
}

TEST(JSONTest, CommandSerialization)
{
    json cmd = {{"cmd", "add_box"},
                {"view_id", "view_123"},
                {"size", std::array<float, 3>{1, 1, 1}},
                {"pos", std::array<float, 3>{0, 0, 0.5f}},
                {"color", std::vector<float>{1, 0, 0}}};

    EXPECT_EQ(cmd["cmd"], "add_box");
    EXPECT_EQ(cmd["view_id"], "view_123");
    EXPECT_EQ(cmd["size"].size(), 3);
    EXPECT_EQ(cmd["color"][0], 1);
}

// ─────────────────────────────────────────────────────────────────────────────
// Client Tests (require running Host)
// ─────────────────────────────────────────────────────────────────────────────

TEST(ClientTest, DISABLED_Connection)
{
    // This test requires a running FrameViz Host
    FrameVizClient client(testutil::resolveTestWsUrl());
    client.connect(std::chrono::seconds(5));
    EXPECT_TRUE(client.isConnected());
    client.close();
}

TEST(ClientTest, DISABLED_SendCommand)
{
    // This test requires a running FrameViz Host
    FrameVizClient client(testutil::resolveTestWsUrl());
    client.connect(std::chrono::seconds(5));

    // Send create_scene command
    json result = client.sendCommand("create_scene", {});
    EXPECT_TRUE(result.contains("scene_id"));

    std::string scene_id = result["scene_id"];
    EXPECT_FALSE(scene_id.empty());

    client.close();
}

TEST(ClientTest, DISABLED_EventHandling)
{
    // This test requires a running FrameViz Host
    FrameVizClient client(testutil::resolveTestWsUrl());
    client.connect(std::chrono::seconds(5));

    bool event_received = false;
    client.onEvent("viewer_ready",
                   [&](const json &data) { event_received = true; });

    // Create view to trigger event
    json result = client.sendCommand("create_scene", {});
    std::string scene_id = result["scene_id"];

    json view_result =
        client.sendCommand("create_view", {{"scene_id", scene_id}});
    std::string view_id = view_result["view_id"];

    if (!tryOpenTauriWindow(view_id, "FrameViz Test", 900, 700,
                            std::nullopt, std::nullopt, "", scene_id)) {
        GTEST_SKIP() << "Tauri control server not available; viewer not started.";
    }

    // Poll events (allow more time for viewer to be ready)
    for (int i = 0; i < 200; i++) {
        client.pollEvents();
        if (event_received) break;
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    EXPECT_TRUE(event_received);
    client.close();
}

TEST(ClientTest, DISABLED_WaitForEventTimeout)
{
    // This test requires a running FrameViz Host
    FrameVizClient client(testutil::resolveTestWsUrl());
    client.connect(std::chrono::seconds(5));

    // Wait for non-existent event (should timeout)
    auto result =
        client.waitForEvent("nonexistent_event", std::chrono::seconds(1));
    EXPECT_FALSE(result.has_value());

    client.close();
}

TEST(ClientTest, DISABLED_WaitForEventWithFilter)
{
    // This test requires a running FrameViz Host
    FrameVizClient client(testutil::resolveTestWsUrl());
    client.connect(std::chrono::seconds(5));

    // Create scene and view
    json scene_result = client.sendCommand("create_scene", {});
    std::string scene_id = scene_result["scene_id"];

    json view_result =
        client.sendCommand("create_view", {{"scene_id", scene_id}});
    std::string view_id = view_result["view_id"];

    if (!tryOpenTauriWindow(view_id, "FrameViz Test", 900, 700,
                            std::nullopt, std::nullopt, "", scene_id)) {
        GTEST_SKIP() << "Tauri control server not available; viewer not started.";
    }

    // Wait for viewer_ready event with specific view_id
    auto event = client.waitForEvent(
        "viewer_ready",
        [&](const json &data) {
            return data.contains("view_id") && data["view_id"] == view_id;
        },
        std::chrono::seconds(15));

    EXPECT_TRUE(event.has_value());
    if (event) {
        EXPECT_EQ((*event)["view_id"], view_id);
    }

    client.close();
}

// ─────────────────────────────────────────────────────────────────────────────
// Viz Integration Tests (require running Host)
// ─────────────────────────────────────────────────────────────────────────────

TEST(VizTest, DISABLED_OpenAndClose)
{
    auto viz = Viz::open();
    EXPECT_FALSE(viz->sceneId().empty());
    EXPECT_FALSE(viz->viewId().empty());
    viz->close();
}

TEST(VizTest, DISABLED_ConnectToExistingView)
{
    FrameVizClient client(testutil::resolveTestWsUrl());
    client.connect(std::chrono::seconds(5));

    json scene_result = client.sendCommand("create_scene", {});
    std::string scene_id = scene_result["scene_id"];
    json view_result = client.sendCommand("create_view", {{"scene_id", scene_id}});
    std::string view_id = view_result["view_id"];

    auto viz = Viz::connect(testutil::resolveTestWsUrl(), view_id,
                            std::chrono::seconds(5));
    EXPECT_EQ(viz->viewId(), view_id);
    EXPECT_EQ(viz->sceneId(), scene_id);
    viz->close();

    json views_after = client.sendCommand("list_views", {});
    bool still_exists = false;
    for (const auto &v : views_after["views"]) {
        if (v.is_object() && v.value("view_id", "") == view_id) {
            still_exists = true;
            break;
        }
    }
    EXPECT_TRUE(still_exists);

    client.sendCommand("destroy_view", {{"view_id", view_id}});
    client.sendCommand("destroy_scene", {{"scene_id", scene_id}});
    client.close();
}

TEST(VizTest, DISABLED_ConnectAutoSelectSingleView)
{
    FrameVizClient client(testutil::resolveTestWsUrl());
    client.connect(std::chrono::seconds(5));
    json existing = client.sendCommand("list_views", {});
    if (existing.contains("views") && existing["views"].is_array() &&
        !existing["views"].empty()) {
        GTEST_SKIP() << "Host already has active views; requires a clean host.";
    }

    json scene_result = client.sendCommand("create_scene", {});
    std::string scene_id = scene_result["scene_id"];
    json view_result = client.sendCommand("create_view", {{"scene_id", scene_id}});
    std::string view_id = view_result["view_id"];

    auto viz = Viz::connect(testutil::resolveTestWsUrl(), "",
                            std::chrono::seconds(5));
    EXPECT_EQ(viz->viewId(), view_id);
    EXPECT_EQ(viz->sceneId(), scene_id);
    viz->close();

    client.sendCommand("destroy_view", {{"view_id", view_id}});
    client.sendCommand("destroy_scene", {{"scene_id", scene_id}});
    client.close();
}

TEST(VizTest, DISABLED_ConnectTimeoutWhenNoView)
{
    FrameVizClient client(testutil::resolveTestWsUrl());
    client.connect(std::chrono::seconds(5));
    json existing = client.sendCommand("list_views", {});
    client.close();

    if (existing.contains("views") && existing["views"].is_array() &&
        !existing["views"].empty()) {
        GTEST_SKIP() << "Host already has active views; requires a clean host.";
    }

    try {
        auto viz = Viz::connect(testutil::resolveTestWsUrl(), "",
                                std::chrono::seconds(1));
        (void)viz;
        FAIL() << "Expected Viz::connect to timeout when no view exists.";
    } catch (const std::runtime_error &err) {
        std::string message = err.what();
        EXPECT_NE(message.find("No available view"), std::string::npos);
    }
}

TEST(VizTest, DISABLED_AddBox)
{
    auto viz = Viz::open();

    Handle box = viz->addBox({1, 1, 1}, {0, 0, 0.5f}, {0, 0, 0, 1}, {1, 0, 0});
    EXPECT_FALSE(box.empty());
    EXPECT_TRUE(viz->isObjectAlive(box));

    viz->close();
}

TEST(VizTest, DISABLED_SetTransform)
{
    auto viz = Viz::open();

    Handle box = viz->addBox();
    viz->setTransform(box, {1, 2, 3}, {0, 0, 0, 1});

    Pose pose = viz->getTransform(box);
    EXPECT_FLOAT_EQ(pose.pos[0], 1.0f);
    EXPECT_FLOAT_EQ(pose.pos[1], 2.0f);
    EXPECT_FLOAT_EQ(pose.pos[2], 3.0f);

    viz->close();
}

TEST(VizTest, DISABLED_RemoveObject)
{
    auto viz = Viz::open();

    Handle box = viz->addBox();
    EXPECT_TRUE(viz->isObjectAlive(box));

    viz->removeObject(box);
    EXPECT_FALSE(viz->isObjectAlive(box));

    viz->close();
}

TEST(VizTest, DISABLED_CloneObject)
{
    auto viz = Viz::open();

    Handle box1 = viz->addBox({1, 1, 1}, {0, 0, 0}, {0, 0, 0, 1}, {1, 0, 0});
    Handle box2 = viz->cloneObject(box1);

    EXPECT_NE(box1, box2);
    EXPECT_TRUE(viz->isObjectAlive(box1));
    EXPECT_TRUE(viz->isObjectAlive(box2));

    viz->close();
}

TEST(VizTest, DISABLED_SetCameraPose)
{
    auto viz = Viz::open();

    if (!viz->waitForViewer(std::chrono::seconds(15))) {
        GTEST_SKIP() << "Viewer not ready; skipping camera pose test.";
    }

    viz->setCameraPose({5, 5, 3}, {0, 0, 0}, {0, 0, 1});

    CameraPose cam = viz->getCameraPose();
    EXPECT_FLOAT_EQ(cam.eye[0], 5.0f);
    EXPECT_FLOAT_EQ(cam.eye[1], 5.0f);
    EXPECT_FLOAT_EQ(cam.eye[2], 3.0f);

    viz->close();
}

TEST(VizTest, DISABLED_AddInstances)
{
    auto viz = Viz::open();

    // Create 100 box instances
    std::vector<float> positions(300); // 100 × 3
    for (size_t i = 0; i < 300; i++) {
        positions[i] = (rand() / (float)RAND_MAX - 0.5f) * 10.0f;
    }

    Handle instances = viz->addInstances(InstanceType::BOX, positions, {}, {},
                                         {}, Color{1.0f, 0.0f, 0.0f}, 0.8f,
                                         Vec3{0.2f, 0.2f, 0.2f});

    EXPECT_FALSE(instances.empty());
    EXPECT_TRUE(viz->isObjectAlive(instances));

    viz->close();
}

TEST(VizTest, DISABLED_UpdateInstances)
{
    auto viz = Viz::open();

    std::vector<float> positions(300); // 100 × 3
    for (size_t i = 0; i < 300; i++) {
        positions[i] = 0.0f;
    }

    Handle instances =
        viz->addInstances(InstanceType::SPHERE, positions, {}, {}, {},
                          Color{0.0f, 1.0f, 0.0f}, 1.0f, std::nullopt);

    // Update positions
    for (size_t i = 0; i < 300; i++) {
        positions[i] = (rand() / (float)RAND_MAX - 0.5f) * 5.0f;
    }

    viz->updateInstances(instances, positions);
    EXPECT_TRUE(viz->isObjectAlive(instances));

    viz->close();
}

TEST(VizTest, DISABLED_BatchTransforms)
{
    auto viz = Viz::open();

    // Create 10 objects
    std::vector<Handle> handles;
    for (int i = 0; i < 10; i++) {
        handles.push_back(viz->addBox());
    }

    // Prepare batch transforms
    std::vector<TransformItem> items;
    for (int i = 0; i < 10; i++) {
        Pose pose{{static_cast<float>(i), 0, 0}, {0, 0, 0, 1}, {1, 1, 1}};
        items.push_back({handles[i], pose});
    }

    viz->setObjectTransforms(items);

    // Verify
    Pose pose5 = viz->getTransform(handles[5]);
    EXPECT_FLOAT_EQ(pose5.pos[0], 5.0f);

    viz->close();
}

} // namespace frameviz
