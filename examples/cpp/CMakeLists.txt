# FrameViz C++ Examples - Root CMakeLists.txt
#
# 一次性构建所有 C++ 示例
#
# 用法：
#   mkdir build && cd build
#   cmake ..
#   make
#
# 所有可执行文件将安装到 build/bin/

cmake_minimum_required(VERSION 3.15)
project(FrameVizCppExamples)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 设置安装目录
set(CMAKE_INSTALL_PREFIX "${CMAKE_BINARY_DIR}" CACHE PATH "Install prefix" FORCE)

# 可执行文件输出到 build/bin/<category>/
# 使用 set_target_properties 在各子目录中设置 RUNTIME_OUTPUT_DIRECTORY

# FrameViz C++ SDK
# Priority 1: Try to find installed SDK (bundle install sets CMAKE_PREFIX_PATH)
# Priority 2: Fallback to monorepo development (add_subdirectory)
find_package(frameviz QUIET)

if(frameviz_FOUND)
    message(STATUS "Using installed FrameViz C++ SDK")
    # Ensure a consistent target name for examples
    if(TARGET frameviz::frameviz-cpp AND NOT TARGET frameviz-cpp)
        add_library(frameviz-cpp ALIAS frameviz::frameviz-cpp)
    endif()
else()
    # Fallback: Use monorepo development build
    set(FRAMEVIZ_CPP_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../packages/frameviz-cpp")
    if(EXISTS "${FRAMEVIZ_CPP_DIR}/CMakeLists.txt")
        message(STATUS "Using FrameViz C++ SDK from monorepo: ${FRAMEVIZ_CPP_DIR}")
        set(FRAMEVIZ_BUILD_TESTS OFF CACHE BOOL "Disable frameviz tests" FORCE)
        add_subdirectory(${FRAMEVIZ_CPP_DIR} frameviz-cpp-build)
    else()
        message(FATAL_ERROR "FrameViz C++ SDK not found. Install it or build from monorepo.")
    endif()
endif()

# 添加所有示例子目录
add_subdirectory(01_basic_primitives/hello_world)
add_subdirectory(01_basic_primitives/colors_and_transparency)
add_subdirectory(01_basic_primitives/instancing)
add_subdirectory(01_basic_primitives/batch_transforms_and_view_status)
add_subdirectory(01_basic_primitives/lines_and_points)
add_subdirectory(01_basic_primitives/mesh_transparency)
add_subdirectory(01_basic_primitives/mesh_smooth_shading)
add_subdirectory(01_basic_primitives/pointcloud_mesh)
add_subdirectory(01_basic_primitives/pcd_pointcloud)
add_subdirectory(01_basic_primitives/resource_cleanup)
add_subdirectory(01_basic_primitives/snapshot_large_buffer)
add_subdirectory(01_basic_primitives/view_config_and_mesh)
add_subdirectory(02_camera_views/multi_view)
add_subdirectory(02_camera_views/camera_controls_fit_object)
add_subdirectory(02_camera_views/multi_view_isolation)
add_subdirectory(03_interaction/gizmo_demo)
add_subdirectory(03_interaction/gizmo_config)
add_subdirectory(03_interaction/picking_demo)
add_subdirectory(04_robotics/octomap_dynamic)
add_subdirectory(04_robotics/robot_arm)

# 打印构建信息
message(STATUS "")
message(STATUS "=================================================")
message(STATUS "FrameViz C++ Examples Build Configuration")
message(STATUS "=================================================")
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "Install prefix: ${CMAKE_INSTALL_PREFIX}")
message(STATUS "")
message(STATUS "Examples to build:")
message(STATUS "  - hello_world")
message(STATUS "  - colors_and_transparency")
message(STATUS "  - instancing")
message(STATUS "  - batch_transforms_and_view_status")
message(STATUS "  - lines_and_points")
message(STATUS "  - mesh_transparency")
message(STATUS "  - mesh_smooth_shading")
message(STATUS "  - pointcloud_mesh")
message(STATUS "  - pcd_pointcloud")
message(STATUS "  - resource_cleanup")
message(STATUS "  - snapshot_large_buffer")
message(STATUS "  - view_config_and_mesh")
message(STATUS "  - multi_view")
message(STATUS "  - camera_controls_fit_object")
message(STATUS "  - multi_view_isolation")
message(STATUS "  - gizmo_demo")
message(STATUS "  - gizmo_config")
message(STATUS "  - picking_demo")
message(STATUS "  - octomap_dynamic")
message(STATUS "  - robot_arm")
message(STATUS "")
message(STATUS "After build, run: make install")
message(STATUS "Executables will be in: ${CMAKE_INSTALL_PREFIX}/bin/")
message(STATUS "=================================================")
message(STATUS "")
