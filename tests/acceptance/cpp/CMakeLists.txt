cmake_minimum_required(VERSION 3.16)
project(frameviz_installed_consumer LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(frameviz 0.4.0 EXACT CONFIG REQUIRED)
add_executable(consumer main.cpp)
target_link_libraries(consumer PRIVATE frameviz::frameviz-cpp)

add_executable(asset_harness asset_harness.cpp ../../../examples/apps/urdf_robot/cpp/src/asset_server.cpp)
target_include_directories(asset_harness PRIVATE ../../../examples/apps/urdf_robot/cpp/include)

add_executable(find_host find_host.cpp)
target_link_libraries(find_host PRIVATE frameviz::frameviz-cpp)

add_executable(version_connect version_connect.cpp)
target_link_libraries(version_connect PRIVATE frameviz::frameviz-cpp)

add_executable(present_view present_view.cpp)
target_link_libraries(present_view PRIVATE frameviz::frameviz-cpp)

add_executable(scene_tree scene_tree.cpp)
target_link_libraries(scene_tree PRIVATE frameviz::frameviz-cpp)
