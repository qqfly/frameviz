cmake_minimum_required(VERSION 3.16)
project(simple_slider_backend VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/build/bin)

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

add_executable(simple_slider_backend
    src/main.cpp
)

target_link_libraries(simple_slider_backend PRIVATE
    frameviz::cpp
)

if(TARGET ixwebsocket::ixwebsocket)
    target_link_libraries(simple_slider_backend PRIVATE ixwebsocket::ixwebsocket)
endif()

if(APPLE)
    target_link_libraries(simple_slider_backend PRIVATE
        "-framework CoreFoundation"
        "-framework Security"
    )
elseif(UNIX)
    find_package(Threads REQUIRED)
    target_link_libraries(simple_slider_backend PRIVATE Threads::Threads)
endif()
