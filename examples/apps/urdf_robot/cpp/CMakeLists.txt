# ─────────────────────────────────────────────────────────────────────────────
# URDF Robot C++ Backend
# Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
# ─────────────────────────────────────────────────────────────────────────────

cmake_minimum_required(VERSION 3.16)
project(urdf_robot_backend VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Output executable to bin/ directory
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/build/bin)

# ─────────────────────────────────────────────────────────────────────────────
# Dependencies
# ─────────────────────────────────────────────────────────────────────────────

include(FetchContent)
set(FETCHCONTENT_UPDATES_DISCONNECTED ON)

# FrameViz C++ SDK
# Priority 1: Use monorepo development build (for latest changes)
# Priority 2: Try to find installed SDK (bundle install sets CMAKE_PREFIX_PATH)
set(FRAMEVIZ_CPP_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../../packages/frameviz-cpp")
if(EXISTS "${FRAMEVIZ_CPP_DIR}/CMakeLists.txt")
    message(STATUS "Using FrameViz C++ SDK from monorepo: ${FRAMEVIZ_CPP_DIR}")
    add_subdirectory(${FRAMEVIZ_CPP_DIR} frameviz-cpp)
else()
    find_package(frameviz 0.5.0 EXACT QUIET)
    if(frameviz_FOUND)
        message(STATUS "Using installed FrameViz C++ SDK")
    else()
        message(FATAL_ERROR "FrameViz C++ SDK not found. Install it or build from monorepo.")
    endif()
endif()

# cpp-httplib: header-only, included in include/ directory
# OpenSSL support is disabled via #undef in asset_server.cpp

# ─────────────────────────────────────────────────────────────────────────────
# Executable
# ─────────────────────────────────────────────────────────────────────────────

add_executable(urdf_robot_backend
    src/main.cpp
    src/robot_model.cpp
    src/robot_visualizer.cpp
    src/ui_server.cpp
    src/asset_server.cpp
)

target_include_directories(urdf_robot_backend PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_link_libraries(urdf_robot_backend PRIVATE
    frameviz::cpp
)

# Platform-specific settings
if(APPLE)
    target_link_libraries(urdf_robot_backend PRIVATE
        "-framework CoreFoundation"
        "-framework Security"
    )
elseif(UNIX)
    find_package(Threads REQUIRED)
    target_link_libraries(urdf_robot_backend PRIVATE Threads::Threads)
endif()
