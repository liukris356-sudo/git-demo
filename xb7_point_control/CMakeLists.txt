cmake_minimum_required(VERSION 3.16)
project(xb7_point_control LANGUAGES CXX)

if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")
  message(FATAL_ERROR "xCoreSDK point tools must be built and run on Linux")
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Threads REQUIRED)

set(XCORE_SDK_ROOT "" CACHE PATH "Root of a complete xCoreSDK 0.7.1 package")
if(NOT XCORE_SDK_ROOT AND DEFINED ENV{XCORE_SDK_ROOT})
  set(XCORE_SDK_ROOT "$ENV{XCORE_SDK_ROOT}")
endif()
if(NOT XCORE_SDK_ROOT)
  message(FATAL_ERROR "Set XCORE_SDK_ROOT to a complete xCoreSDK package")
endif()

if(NOT EXISTS "${XCORE_SDK_ROOT}/include/rokae/robot.h")
  message(FATAL_ERROR "Missing xCoreSDK headers under ${XCORE_SDK_ROOT}")
endif()
if(NOT CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|aarch64)$")
  message(FATAL_ERROR "Unsupported CPU architecture: ${CMAKE_SYSTEM_PROCESSOR}")
endif()

set(XCORE_ARCH_DIR "${XCORE_SDK_ROOT}/lib/Linux/${CMAKE_SYSTEM_PROCESSOR}")
set(XCORE_LIBRARY "${XCORE_ARCH_DIR}/libxCoreSDK.a")
set(XMATE_MODEL_LIBRARY "${XCORE_ARCH_DIR}/libxMateModel.a")
if(NOT EXISTS "${XCORE_LIBRARY}")
  message(FATAL_ERROR
    "Missing ${XCORE_LIBRARY}. The GitHub source archive contains headers and "
    "examples but may omit release libraries; obtain the matching full SDK.")
endif()
if(NOT EXISTS "${XMATE_MODEL_LIBRARY}")
  message(FATAL_ERROR "Missing ${XMATE_MODEL_LIBRARY}")
endif()

function(add_xb7_tool target source)
  add_executable(${target} ${source})
  target_include_directories(${target} PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/include"
    "${XCORE_SDK_ROOT}/include"
    "${XCORE_SDK_ROOT}/external")
  target_compile_definitions(${target} PRIVATE EIGEN_DONT_ALIGN_STATICALLY)
  target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
  target_link_libraries(${target} PRIVATE
    "${XCORE_LIBRARY}"
    "${XMATE_MODEL_LIBRARY}"
    Threads::Threads
    ${CMAKE_DL_LIBS})
endfunction()

add_xb7_tool(xb7_point_recorder src/xb7_point_recorder.cpp)
add_xb7_tool(xb7_point_player src/xb7_point_player.cpp)
add_xb7_tool(xb7_frame_inspector src/xb7_frame_inspector.cpp)
add_xb7_tool(xb7_fixed_j6_inspector src/xb7_fixed_j6_inspector.cpp)
