cmake_minimum_required(VERSION 3.15)
project(camera_controls_fit_object)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find frameviz-cpp (only add if not already added by parent CMakeLists)
if(NOT TARGET frameviz-cpp)
    # Priority 1: Try to find installed SDK
    find_package(frameviz QUIET)

    if(frameviz_FOUND)
        message(STATUS "Using installed FrameViz C++ SDK")
        # Create alias if needed
        if(TARGET frameviz::frameviz-cpp AND NOT TARGET frameviz-cpp)
            add_library(frameviz-cpp ALIAS frameviz::frameviz-cpp)
        endif()
    else()
        # Priority 2: Fallback to monorepo development build
        set(FRAMEVIZ_CPP_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../../packages/frameviz-cpp")
        if(EXISTS "${FRAMEVIZ_CPP_DIR}/CMakeLists.txt")
            message(STATUS "Using FrameViz C++ SDK from monorepo: ${FRAMEVIZ_CPP_DIR}")
            set(FRAMEVIZ_BUILD_TESTS OFF CACHE BOOL "Disable frameviz tests" FORCE)
            add_subdirectory(${FRAMEVIZ_CPP_DIR} frameviz-cpp-build)
        else()
            message(FATAL_ERROR "FrameViz C++ SDK not found. Install it or build from monorepo.")
        endif()
    endif()
endif()

add_executable(camera_controls_fit_object main.cpp)
target_link_libraries(camera_controls_fit_object PRIVATE frameviz-cpp)

# Output to build/bin/02_camera_views/
set_target_properties(camera_controls_fit_object PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin/02_camera_views"
)

install(TARGETS camera_controls_fit_object DESTINATION bin/02_camera_views)
