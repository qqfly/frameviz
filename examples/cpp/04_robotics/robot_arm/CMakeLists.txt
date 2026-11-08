cmake_minimum_required(VERSION 3.15)
project(robot_arm)

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

add_executable(robot_arm main.cpp)
target_link_libraries(robot_arm PRIVATE frameviz-cpp)

# Output to build/bin/04_robotics/
set_target_properties(robot_arm PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin/04_robotics"
)

install(TARGETS robot_arm DESTINATION bin/04_robotics)
