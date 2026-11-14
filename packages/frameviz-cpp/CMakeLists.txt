# ─────────────────────────────────────────────────────────────────────────────
# FrameViz C++ SDK build configuration
# Copyright © 2026 qqfly. SPDX-License-Identifier: MIT
# ─────────────────────────────────────────────────────────────────────────────

cmake_minimum_required(VERSION 3.16)
project(frameviz-cpp VERSION 0.5.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# ═══════════════════════════════════════════════════════════════════════════
# Installation path follows CMAKE_INSTALL_PREFIX
# ═══════════════════════════════════════════════════════════════════════════
# Honor the consumer's install prefix and do not enable tests when embedded.
if(CMAKE_SOURCE_DIR STREQUAL PROJECT_SOURCE_DIR)
    set(FRAMEVIZ_TESTS_DEFAULT ON)
else()
    set(FRAMEVIZ_TESTS_DEFAULT OFF)
endif()
option(FRAMEVIZ_BUILD_TESTS "Build tests" ${FRAMEVIZ_TESTS_DEFAULT})
option(FRAMEVIZ_BUILD_SHARED "Build shared library (default: static)" OFF)

# Dependencies
include(FetchContent)

# Use offline mode after first download to speed up builds
set(FETCHCONTENT_UPDATES_DISCONNECTED ON)

# nlohmann_json is bundled (header-only)
# The single-header file is included in third_party/nlohmann/json.hpp
# We include it directly in frameviz-cpp target instead of creating a separate target

# Threads (required for system ixwebsocket on Linux)
find_package(Threads REQUIRED)

# IXWebSocket (Force static build)
find_package(IXWebSocket QUIET)
if(NOT IXWebSocket_FOUND)
    message(STATUS "IXWebSocket not found in system, using FetchContent")

    # Force static library for ixwebsocket
    set(USE_TLS OFF)
    set(USE_ZLIB OFF)
    set(BUILD_SHARED_LIBS OFF)

    FetchContent_Declare(
        ixwebsocket
        GIT_REPOSITORY https://github.com/machinezone/IXWebSocket.git
        GIT_TAG v11.4.5
        GIT_SHALLOW TRUE
    )
    FetchContent_MakeAvailable(ixwebsocket)

    # Create alias if not exists
    if(NOT TARGET ixwebsocket::ixwebsocket)
        add_library(ixwebsocket::ixwebsocket ALIAS ixwebsocket)
    endif()
else()
    message(STATUS "Found system IXWebSocket")
endif()

# ═══════════════════════════════════════════════════════════════════════════
# FrameViz C++ Library (Static by default)
# ═══════════════════════════════════════════════════════════════════════════

if(FRAMEVIZ_BUILD_SHARED)
    add_library(frameviz-cpp SHARED
        src/client.cpp
        src/viz.cpp
        src/buffer.cpp
        src/discovery.cpp
        src/tauri.cpp
        src/host.cpp
        src/capture.cpp
    )
    set_target_properties(frameviz-cpp PROPERTIES
        VERSION ${PROJECT_VERSION}
        SOVERSION 0
    )
else()
    add_library(frameviz-cpp STATIC
        src/client.cpp
        src/viz.cpp
        src/buffer.cpp
        src/discovery.cpp
        src/tauri.cpp
        src/host.cpp
        src/capture.cpp
    )
endif()

target_include_directories(frameviz-cpp
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/third_party>
        $<INSTALL_INTERFACE:include>
)

# Link dependencies (ixwebsocket is private, statically linked)
target_link_libraries(frameviz-cpp
    PRIVATE
        ixwebsocket::ixwebsocket
)
if(APPLE)
    target_link_libraries(frameviz-cpp PRIVATE "-framework CoreFoundation")
elseif(WIN32)
    target_compile_definitions(frameviz-cpp PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN)
    target_link_libraries(frameviz-cpp PRIVATE advapi32 shell32 version ws2_32)
endif()

# Add aliases for easy linking (support both naming conventions)
add_library(frameviz::frameviz-cpp ALIAS frameviz-cpp)
add_library(frameviz::cpp ALIAS frameviz-cpp)

# ═══════════════════════════════════════════════════════════════════════════
# Installation
# ═══════════════════════════════════════════════════════════════════════════

include(GNUInstallDirs)

# Install library
install(TARGETS frameviz-cpp
    EXPORT frameviz-targets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

# Install headers
install(DIRECTORY include/
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
    FILES_MATCHING PATTERN "*.hpp"
)

# Install bundled nlohmann_json header
install(DIRECTORY third_party/nlohmann
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
    FILES_MATCHING PATTERN "*.hpp"
)

# TARGET_FILE resolves imported per-configuration locations as well as local builds.
if(TARGET ixwebsocket::ixwebsocket)
    install(FILES $<TARGET_FILE:ixwebsocket::ixwebsocket>
        DESTINATION ${CMAKE_INSTALL_LIBDIR})
    get_target_property(IXWEBSOCKET_INCLUDE_DIRS ixwebsocket::ixwebsocket INTERFACE_INCLUDE_DIRECTORIES)
    foreach(directory IN LISTS IXWEBSOCKET_INCLUDE_DIRS)
        if(EXISTS "${directory}/ixwebsocket")
            install(DIRECTORY "${directory}/ixwebsocket" DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
                FILES_MATCHING PATTERN "*.h")
        endif()
    endforeach()
endif()

# Generate and install CMake config files
install(EXPORT frameviz-targets
    FILE frameviz-targets.cmake
    NAMESPACE frameviz::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/frameviz
)

# Generate config file
include(CMakePackageConfigHelpers)

configure_package_config_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/cmake/frameviz-config.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/frameviz-config.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/frameviz
)

write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/frameviz-config-version.cmake
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/frameviz-config.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/frameviz-config-version.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/frameviz
)

# Tests
if(FRAMEVIZ_BUILD_TESTS)
    enable_testing()
    FetchContent_Declare(
        googletest
        GIT_REPOSITORY https://github.com/google/googletest.git
        GIT_TAG v1.14.0
    )
    FetchContent_MakeAvailable(googletest)
    
    add_executable(test_client tests/test_client.cpp)
    target_link_libraries(test_client PRIVATE frameviz-cpp GTest::gtest_main)

    add_executable(test_concurrency tests/test_concurrency.cpp)
    target_link_libraries(test_concurrency PRIVATE frameviz-cpp GTest::gtest_main)

    include(GoogleTest)
    gtest_discover_tests(test_client)
    gtest_discover_tests(test_concurrency)
endif()

install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/LICENSE" "${CMAKE_CURRENT_SOURCE_DIR}/NOTICE" DESTINATION ${CMAKE_INSTALL_DATADIR}/frameviz)
install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/../../THIRD_PARTY_LICENSES/" DESTINATION ${CMAKE_INSTALL_DATADIR}/frameviz/licenses)
