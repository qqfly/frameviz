cmake_minimum_required(VERSION 3.16)
project(frameviz_external_backend VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/build/bin)

find_package(frameviz 0.4.0 EXACT QUIET)
if(NOT frameviz_FOUND)
  # Monorepo fallback for local verification; external usage should rely on installed SDK.
  set(FRAMEVIZ_CPP_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../packages/frameviz-cpp")
  if(EXISTS "${FRAMEVIZ_CPP_DIR}/CMakeLists.txt")
    message(STATUS "Using FrameViz C++ SDK from monorepo: ${FRAMEVIZ_CPP_DIR}")
    add_subdirectory(${FRAMEVIZ_CPP_DIR} frameviz-cpp)
  else()
    message(FATAL_ERROR "FrameViz C++ SDK not found. Install frameviz-cpp SDK and ensure CMAKE_PREFIX_PATH is set.")
  endif()
endif()

find_package(IXWebSocket QUIET)
if(NOT TARGET ixwebsocket::ixwebsocket)
  include(FetchContent)
  set(USE_TLS OFF CACHE BOOL "" FORCE)
  set(USE_ZLIB OFF CACHE BOOL "" FORCE)
  set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
  FetchContent_Declare(
    ixwebsocket
    GIT_REPOSITORY https://github.com/machinezone/IXWebSocket.git
    GIT_TAG v11.4.5
    GIT_SHALLOW TRUE
  )
  FetchContent_MakeAvailable(ixwebsocket)
  if(NOT TARGET ixwebsocket::ixwebsocket)
    add_library(ixwebsocket::ixwebsocket ALIAS ixwebsocket)
  endif()
endif()

add_executable(frameviz_external_backend
  src/main.cpp
)
set_property(TARGET frameviz_external_backend PROPERTY NO_SYSTEM_FROM_IMPORTED ON)

# Ensure the selected FrameViz SDK headers are searched before any global
# locations (e.g. /usr/local/include) that may contain stale headers.
if(TARGET frameviz::cpp)
  get_target_property(FRAMEVIZ_INCLUDE_DIRS frameviz::cpp INTERFACE_INCLUDE_DIRECTORIES)
  if(FRAMEVIZ_INCLUDE_DIRS)
    target_include_directories(frameviz_external_backend BEFORE PRIVATE ${FRAMEVIZ_INCLUDE_DIRS})
    foreach(FRAMEVIZ_INC ${FRAMEVIZ_INCLUDE_DIRS})
      target_compile_options(frameviz_external_backend PRIVATE "-I${FRAMEVIZ_INC}")
    endforeach()
  endif()
endif()

target_link_libraries(frameviz_external_backend PRIVATE
  frameviz::cpp
  ixwebsocket::ixwebsocket
)

if(APPLE)
  target_link_libraries(frameviz_external_backend PRIVATE
    "-framework CoreFoundation"
    "-framework Security"
  )
elseif(UNIX)
  find_package(Threads REQUIRED)
  target_link_libraries(frameviz_external_backend PRIVATE Threads::Threads)
endif()
