/**
 * @file viz.hpp
 * @brief High-level FrameViz visualization API
 *
 * Maintainer: qqfly
 * @date 2026-01-25
 * @bug No known bugs
 *
 * @copyright Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
 */

#ifndef FRAMEVIZ_CPP_VIZ_HPP
#define FRAMEVIZ_CPP_VIZ_HPP

#include <memory>
#include <optional>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "client.hpp"
#include "types.hpp"

namespace frameviz {

struct SceneNodeOptions {
  std::optional<Handle> parent;
  std::optional<std::string> name;
  json tags = json::object();
  std::optional<RigidPose> pose;
  std::optional<Vec3> geometryScale;
};

/**
 * @brief High-level FrameViz visualization context.
 *
 * Provides a convenient API for creating primitives, managing transforms,
 * and handling user interaction events.
 */
class Viz {
public:
  /**
   * @brief Open a connection to FrameViz Host and create a Viz instance.
   * @param url WebSocket URL (default: ws://127.0.0.1:9527)
   * @param title Window title
   * @param width Window width
   * @param height Window height
   * @param windowDecorations Whether to show window title bar and borders (default: true)
   * @param shareScene If provided, bind to an existing scene instead of creating a new one.
   *                   This allows multiple views to share the same scene data while having
   *                   independent cameras. (default: create new scene)
   * @param windowMode Controls automatic window opening behavior:
   *                   0 - Don't open window (manual open required)
   *                   1 - Open browser automatically
   *                   2 - Try Tauri first, fallback to browser (default)
   * @return Unique pointer to Viz instance
   *
   * Example:
   *   // Create first view with new scene
   *   auto viz1 = Viz::open();
   *   // Create second view sharing the same scene
   *   auto viz2 = Viz::open("Title", 800, 600, true, viz1->sceneId());
   */
  static std::unique_ptr<Viz>
  open(const std::string &url = "ws://127.0.0.1:9527",
       const std::string &title = "FrameViz", int width = 800,
       int height = 600, bool windowDecorations = true,
       const std::optional<std::string>& shareScene = std::nullopt,
       int windowMode = 2, bool autoEvents = true);

  /**
   * @brief Connect to an existing view and return a Viz instance.
   *
   * This is the embedded-mode counterpart of open(). It does not create
   * a scene/view, and instead binds to an already-existing view.
   *
   * @param url WebSocket URL (default: ws://127.0.0.1:9527)
   * @param view_id Optional target view identifier.
   *                If empty, connect succeeds only when exactly one view exists.
   * @param timeout Maximum time to wait for view availability.
   * @return Unique pointer to Viz instance
   *
   * Example:
   *   auto viz = Viz::connect("ws://127.0.0.1:9527", "v_1");
   *   viz->addBox({0, 0, 0});
   */
  static std::unique_ptr<Viz>
  connect(const std::string &url = "ws://127.0.0.1:9527",
          const std::string &view_id = "",
          std::chrono::seconds timeout = std::chrono::seconds(10),
          bool autoEvents = true);

  /**
   * @brief Destructor.
   */
  ~Viz();

  // Non-copyable
  Viz(const Viz &) = delete;
  Viz &operator=(const Viz &) = delete;

  // Movable
  Viz(Viz &&) noexcept;
  Viz &operator=(Viz &&) noexcept;

  // ─────────────────────────────────────────────────────────────────────────
  // Scene / View IDs
  // ─────────────────────────────────────────────────────────────────────────

  std::string sceneId() const;
  std::string viewId() const;
  bool waitForViewer(std::chrono::seconds timeout = std::chrono::seconds(10));
  // Close view and auto-destroy scene when last view closes.
  void close();

  // ─────────────────────────────────────────────────────────────────────────
  // Primitives
  // ─────────────────────────────────────────────────────────────────────────

  Handle addBox(Vec3 size = {1.0f, 1.0f, 1.0f},
                Vec3 pos = {0.0f, 0.0f, 0.0f},
                Quat quat = {0.0f, 0.0f, 0.0f, 1.0f},
                Color color = {1.0f, 1.0f, 1.0f},
                  const SceneNodeOptions &node = {});

  Handle addSphere(float radius = 0.5f, Vec3 pos = {0.0f, 0.0f, 0.0f},
                   Quat quat = {0.0f, 0.0f, 0.0f, 1.0f},
                   Color color = {1.0f, 1.0f, 1.0f},
                  const SceneNodeOptions &node = {});

  Handle addCylinder(float radius = 0.5f, float height = 1.0f,
                     Vec3 pos = {0.0f, 0.0f, 0.0f},
                     Quat quat = {0.0f, 0.0f, 0.0f, 1.0f},
                     Color color = {1.0f, 1.0f, 1.0f},
                  const SceneNodeOptions &node = {});

  Handle addCone(float radius = 0.5f, float height = 1.0f,
                 Vec3 pos = {0.0f, 0.0f, 0.0f},
                 Quat quat = {0.0f, 0.0f, 0.0f, 1.0f},
                 Color color = {1.0f, 1.0f, 1.0f},
                  const SceneNodeOptions &node = {});

  Handle addAxes(float length = 1.0f, float radius = 0.02f,
                 Vec3 pos = {0.0f, 0.0f, 0.0f},
                 Quat quat = {0.0f, 0.0f, 0.0f, 1.0f},
                  const SceneNodeOptions &node = {});

  Handle addArrow(Vec3 start = {0.0f, 0.0f, 0.0f},
                  Vec3 end = {0.0f, 0.0f, 1.0f},
                  float radius = 0.05f,
                  Color color = {1.0f, 1.0f, 1.0f},
                  const SceneNodeOptions &node = {});

  Handle addPlane(float width = 1.0f, float height = 1.0f,
                  Vec3 pos = {0.0f, 0.0f, 0.0f},
                  Quat quat = {0.0f, 0.0f, 0.0f, 1.0f},
                  Color color = {0.5f, 0.5f, 0.5f},
                  const SceneNodeOptions &node = {});

  // ─────────────────────────────────────────────────────────────────────────
  // Points / Lines / Mesh
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * @brief Add a point cloud with a uniform color.
   *
   * @param positions Point positions (N * 3 floats)
   * @param color Uniform RGB/RGBA color (0..1)
   * @param size Point size (pixels)
   */
  Handle addPoints(const std::vector<float> &positions,
                   Color color = {1.0f, 1.0f, 1.0f}, float size = 1.0f,
                  const SceneNodeOptions &node = {});

  /**
   * @brief Add a point cloud with per-point colors.
   *
   * @param positions Point positions (N * 3 floats)
   * @param colors Per-point RGB colors (N entries, each 0..1)
   * @param size Point size (pixels)
   */
  Handle addPoints(const std::vector<float> &positions,
                   const std::vector<Color> &colors, float size = 1.0f,
                  const SceneNodeOptions &node = {});

  Handle addLines(const std::vector<float> &positions,
                  const std::vector<uint32_t> &indices = {}, float width = 1.0f,
                  Color color = {1.0f, 1.0f, 1.0f},
                  const SceneNodeOptions &node = {});

  /**
   * @brief Add a triangular or polygon mesh to the scene.
   *
   * @param vertices Vertex positions (V * 3 floats)
   * @param faces Triangle indices (F * 3 uint32) for TRI format
   * @param format TRI (default) or POLY format
   * @param color Uniform RGB/RGBA color for all vertices
   * @param face_colors Per-face colors (RGB, must match face count)
   * @param alpha Optional opacity (0.0=transparent, 1.0=opaque, default=opaque).
   *              If provided, alpha takes precedence over color[3].
   * @param wireframe Show edge lines (default=false, requires extra geometry)
   * @param smooth_shading Enable smooth shading (default=true). When false,
   *                       flat shading is used for a faceted look.
   * @return Object handle
   *
   * Notes:
   * - color and face_colors are mutually exclusive (face_colors takes precedence).
   * - If color is RGBA and alpha is not provided, color[3] is used as alpha.
   *
   * Performance note: wireframe=true creates additional geometry (WireframeGeometry),
   * which doubles memory usage for the mesh. Use sparingly for large meshes.
   */
  Handle addMesh(const std::vector<float> &vertices,
                 const std::vector<uint32_t> &faces,
                 FacesFormat format = FacesFormat::TRI,
                 Color color = {1.0f, 1.0f, 1.0f},
                 const std::vector<Color> &face_colors = {},
                 std::optional<float> alpha = std::nullopt,
                 bool wireframe = false,
                 bool smooth_shading = true,
                  const SceneNodeOptions &node = {});

  Handle loadMesh(const std::string &url, Vec3 pos = {0.0f, 0.0f, 0.0f},
                  Quat quat = {0.0f, 0.0f, 0.0f, 1.0f},
                  Vec3 scale = {1.0f, 1.0f, 1.0f},
                  std::optional<Color> color = std::nullopt,
                  const SceneNodeOptions &node = {});

  // ─────────────────────────────────────────────────────────────────────────
  // Instancing
  // ─────────────────────────────────────────────────────────────────────────

  Handle addInstances(InstanceType type, const std::vector<float> &positions,
                      const std::vector<float> &quats = {},
                      const std::vector<float> &scales = {},
                      const std::vector<Color> &colors = {},
                      std::optional<Color> uniform_color = std::nullopt,
                      std::optional<float> alpha = std::nullopt,
                      const std::optional<Vec3> &size = std::nullopt,
                  const SceneNodeOptions &node = {});

  void updateInstances(Handle handle, const std::vector<float> &positions = {},
                       const std::vector<float> &quats = {},
                       const std::vector<float> &scales = {},
                       const std::vector<Color> &colors = {},
                       std::optional<Color> uniform_color = std::nullopt,
                       std::optional<float> alpha = std::nullopt);

  // ─────────────────────────────────────────────────────────────────────────
  // Transforms
  // ─────────────────────────────────────────────────────────────────────────

  Handle addNode(const SceneNodeOptions &node = {});
  void setParent(Handle handle, const std::optional<Handle> &parent,
                 const std::optional<RigidPose> &localTransform = std::nullopt);
  void setObjectMetadata(Handle handle, const std::optional<std::string> &name,
                         const json &tags);
  void setGeometryScale(Handle handle, Vec3 scale);
  void setTransform(Handle handle, Vec3 pos, Quat quat);
  void setTransform(Handle handle, const RigidPose &pose);

  void setObjectTransforms(const std::vector<TransformItem> &items);

  Pose getTransform(Handle handle, TransformSpace space = TransformSpace::Local);
  // Flat column-major rigid transform.
  std::array<double, 16> getTransformMatrix(
      Handle handle, TransformSpace space = TransformSpace::Local);
  /**
   * @brief Get the uniform RGBA color of an object.
   *
   * @return std::nullopt if the object uses per-vertex/per-face/per-point colors.
   */
  std::optional<Color> getColor(Handle handle);

  /**
   * @brief Get the alpha (transparency) of an object.
   */
  float getAlpha(Handle handle);

  // ─────────────────────────────────────────────────────────────────────────
  // Object Management
  // ─────────────────────────────────────────────────────────────────────────

  void removeObject(Handle handle);

  void removeObjects(const std::vector<Handle> &handles);

  void clear();

  Handle cloneObject(Handle handle);

  bool isObjectAlive(Handle handle);

  void setColor(Handle handle, Color rgba);

  void setAlpha(Handle handle, float alpha);

  void setVisible(Handle handle, bool visible);

  // ─────────────────────────────────────────────────────────────────────────
  // Camera
  // ─────────────────────────────────────────────────────────────────────────

  void setCameraPose(Vec3 eye, Vec3 target, Vec3 up);

  /**
   * @brief Query the current camera pose for this view.
   *
   * Returns default values if the viewer is not ready or no response is available.
   * Throws std::runtime_error on connection/protocol errors.
   */
  CameraPose getCameraPose();

  void resetCamera(const std::string &mode = "fit_scene",
                   const std::string &fit_handle = "");

  // ─────────────────────────────────────────────────────────────────────────
  // View Configuration
  // ─────────────────────────────────────────────────────────────────────────

  void setViewConfig(const json &config);

  json getViewConfig();

  void setView(const std::string &view_preset, bool fit_all = true);

  void setRenderMode(const std::string &mode);

  // ─────────────────────────────────────────────────────────────────────────
  // Camera Controls
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * @brief Configure camera controls for this view.
   *
   * Supported keys (flat JSON):
   * - rotate_sensitivity (default: 0.5)
   * - pan_sensitivity (default: 1.0)
   * - zoom_sensitivity (default: 1.0)
   * - zoom_to_cursor (default: false)
   * - orbit_enabled, pan_enabled, zoom_enabled (default: true)
   * - damping (default: false)
   * - mouse_preset: "cad" or "trackpad"
   * - mouse_buttons: {left, middle, right} = rotate/pan/zoom/none
   * - fov (default: 30)
   */
  void setCameraControls(const json &config);

  json getCameraControls();

  // ─────────────────────────────────────────────────────────────────────────
  // Picking
  // ─────────────────────────────────────────────────────────────────────────

  void setPickConfig(const json &config);

  /**
   * @brief Get current pick configuration for this view.
   *
   * Returns default values if the viewer is not ready or no response is available.
   * Throws std::runtime_error on connection/protocol errors.
   */
  json getPickConfig();

  // ─────────────────────────────────────────────────────────────────────────
  // Text
  // ─────────────────────────────────────────────────────────────────────────

  Handle addText3D(const std::string &text, Vec3 pos, int font_size = 14,
                   Color color = {1.0f, 1.0f, 1.0f},
                   const std::optional<std::string> &background_color = std::nullopt,
                  const SceneNodeOptions &node = {});

  Handle addText2D(const std::string &text, int x = 10, int y = 10,
                   int font_size = 14, Color color = {1.0f, 1.0f, 1.0f});

  // ─────────────────────────────────────────────────────────────────────────
  // Gizmo
  // ─────────────────────────────────────────────────────────────────────────

  void attachGizmo(Handle handle,
                   std::optional<int> mask = std::nullopt,
                   float size = 1.0f,
                   std::optional<std::string> scale_mode = std::nullopt);

  void setGizmoMode(std::optional<int> mask = std::nullopt,
                    std::optional<float> size = std::nullopt,
                    std::optional<std::string> scale_mode = std::nullopt);

  void detachGizmo();

  // ─────────────────────────────────────────────────────────────────────────
  // Events
  // ─────────────────────────────────────────────────────────────────────────

  Handle addWidget(const std::string &kind, const std::string &label,
                   const json &value = nullptr, const json &options = json::object());
  json listWidgets();
  json getWidget(const Handle &widget);
  json getWidgetValue(const Handle &widget);
  void setWidgetValue(const Handle &widget, const json &value, bool emit = false);
  void removeWidget(const Handle &widget);
  void onWidgetChange(const Handle &widget, EventHandler handler, bool append = false);
  void offWidgetChange(const Handle &widget);

  json getCameraView();
  void setCameraView(const json &cameraView);
  json getDisplayState(bool includeBounds = false);

  void onEvent(const std::string &name, EventHandler handler);

  void pollEvents();

  std::optional<json> waitForEvent(const std::string &event_name,
                               std::chrono::seconds timeout = std::chrono::seconds(2));

  std::optional<json> waitForEvent(const std::string &event_name,
                               std::function<bool(const json &)> filter,
                               std::chrono::seconds timeout = std::chrono::seconds(2));

private:
  Viz(std::unique_ptr<FrameVizClient> client, const std::string &scene_id,
      const std::string &view_id, bool opened_via_tauri, bool owns_view,
      bool owns_scene);

  BufferRef uploadBuffer(const void *data, size_t size_bytes,
                         const std::string &dtype,
                         const std::vector<int> &shape,
                         std::vector<std::string> *pending = nullptr);

  Handle addPrimitive(const std::string &ptype, const json &params, Vec3 pos,
                      Quat quat, Color color, const SceneNodeOptions &node);
  Handle addPointCloud(const std::vector<float> &positions,
                       const std::vector<Color> &colors, float size,
                       std::optional<Color> uniformColor, const SceneNodeOptions &node);

private:
  std::unique_ptr<FrameVizClient> m_client;
  std::string m_sceneId;
  std::string m_viewId;
  int m_bufferCounter;
  bool m_openedViaTauri;
  bool m_ownsView = true;
  bool m_ownsScene = false;
  std::unordered_set<Handle> m_overlayHandles;
  bool m_warnedCameraPoseFallback = false;
  bool m_warnedPickConfigFallback = false;
};

} // namespace frameviz

#endif // FRAMEVIZ_CPP_VIZ_HPP
