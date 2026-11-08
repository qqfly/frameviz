cmake_minimum_required(VERSION 3.15)
project(mesh_transparency)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find frameviz-cpp (only add if not already added by parent CMakeLists)
if(NOT TARGET frameviz-cpp)
    # This example requires the latest monorepo version with alpha/wireframe support
    set(FRAMEVIZ_CPP_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../../packages/frameviz-cpp")
    if(EXISTS "${FRAMEVIZ_CPP_DIR}/CMakeLists.txt")
        message(STATUS "Using FrameViz C++ SDK from monorepo: ${FRAMEVIZ_CPP_DIR}")
        set(FRAMEVIZ_BUILD_TESTS OFF CACHE BOOL "Disable frameviz tests" FORCE)
        add_subdirectory(${FRAMEVIZ_CPP_DIR} frameviz-cpp-build)
    else()
        message(FATAL_ERROR "This example requires FrameViz C++ SDK from monorepo. "
                            "Please build from source: ${FRAMEVIZ_CPP_DIR}")
    endif()
endif()

add_executable(mesh_transparency main.cpp)
target_link_libraries(mesh_transparency PRIVATE frameviz-cpp)

# Output to build/bin/01_basic_primitives/
set_target_properties(mesh_transparency PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin/01_basic_primitives"
)

install(TARGETS mesh_transparency DESTINATION bin/01_basic_primitives)
