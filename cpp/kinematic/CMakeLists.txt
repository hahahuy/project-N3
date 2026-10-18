cmake_minimum_required(VERSION 3.20)
project(r2s_kinematic LANGUAGES CXX)

include(CTest)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(r2s_kinematic STATIC kernel.cpp)
target_include_directories(r2s_kinematic PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(r2s_kinematic PRIVATE -Wall -Wextra -Wpedantic)

add_executable(r2s-kinematic-cli cli.cpp)
target_link_libraries(r2s-kinematic-cli PRIVATE r2s_kinematic)
target_compile_options(r2s-kinematic-cli PRIVATE -Wall -Wextra -Wpedantic)

add_executable(r2s-kinematic-smoke smoke_test.cpp)
target_link_libraries(r2s-kinematic-smoke PRIVATE r2s_kinematic)
target_compile_options(r2s-kinematic-smoke PRIVATE -Wall -Wextra -Wpedantic)

if(BUILD_TESTING)
  add_test(NAME r2s-kinematic-smoke COMMAND r2s-kinematic-smoke)
endif()
