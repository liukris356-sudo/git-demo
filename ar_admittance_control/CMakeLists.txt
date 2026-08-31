cmake_minimum_required(VERSION 3.16)
project(ar_admittance_control LANGUAGES CXX)

if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")
  message(FATAL_ERROR "The live xCoreSDK controller must be built and run on Linux.")
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(Threads REQUIRED)

set(XCORE_SDK_ROOT "" CACHE PATH "Root of xCoreSDK-v0.7.1.ar_6")
if(NOT XCORE_SDK_ROOT)
  if(DEFINED ENV{XCORE_SDK_ROOT})
    set(XCORE_SDK_ROOT "$ENV{XCORE_SDK_ROOT}")
  else()
    message(FATAL_ERROR
      "Set XCORE_SDK_ROOT, for example: --cmake-args "
      "-DXCORE_SDK_ROOT=$HOME/projects/AR5-R-flexible-assembly")
  endif()
endif()

if(NOT EXISTS "${XCORE_SDK_ROOT}/include/rokae/robot.h")
  message(FATAL_ERROR "Invalid XCORE_SDK_ROOT: ${XCORE_SDK_ROOT}")
endif()
if(NOT EXISTS "${XCORE_SDK_ROOT}/external/Eigen/Core")
  message(FATAL_ERROR
    "Bundled Eigen headers not found: ${XCORE_SDK_ROOT}/external/Eigen/Core")
endif()

if(NOT CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|aarch64)$")
  message(FATAL_ERROR "Unsupported CPU architecture: ${CMAKE_SYSTEM_PROCESSOR}")
endif()

set(XCORE_ARCH_DIR "${XCORE_SDK_ROOT}/lib/Linux/${CMAKE_SYSTEM_PROCESSOR}")
set(XCORE_STATIC_LIBRARY "${XCORE_ARCH_DIR}/libxCoreSDK.a")
set(XMATE_MODEL_LIBRARY "${XCORE_ARCH_DIR}/libxMateModel.a")
if(NOT EXISTS "${XCORE_STATIC_LIBRARY}")
  message(FATAL_ERROR "xCoreSDK library not found: ${XCORE_STATIC_LIBRARY}")
endif()
if(NOT EXISTS "${XMATE_MODEL_LIBRARY}")
  message(FATAL_ERROR "xMateModel library not found: ${XMATE_MODEL_LIBRARY}")
endif()

function(add_ar_admittance_node target)
  add_executable(${target} ${ARGN})
  target_include_directories(${target} PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/include"
    "${XCORE_SDK_ROOT}/include"
    "${XCORE_SDK_ROOT}/external")
  target_compile_definitions(${target} PRIVATE EIGEN_DONT_ALIGN_STATICALLY)
  ament_target_dependencies(${target} geometry_msgs rclcpp std_msgs)
  target_link_libraries(${target}
    "${XCORE_STATIC_LIBRARY}"
    "${XMATE_MODEL_LIBRARY}"
    Threads::Threads
    ${CMAKE_DL_LIBS})
  target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
endfunction()

add_ar_admittance_node(ar_admittance_z_node
  src/ar_admittance_z_node.cpp)
add_ar_admittance_node(ar_admittance_cartesian_6d_node
  src/ar_admittance_cartesian_6d_node.cpp)
add_ar_admittance_node(ar_admittance_joint_6d_node
  src/ar_admittance_joint_6d_node.cpp)
add_ar_admittance_node(ar_assembly_force_guard_node
  src/ar_assembly_force_guard_node.cpp
  src/ar_four_point_smooth_trajectory_guarded.cpp)
target_include_directories(ar_assembly_force_guard_node PRIVATE
  "${XCORE_SDK_ROOT}/example/ar_control_suite"
  "${XCORE_SDK_ROOT}/example/rt")
target_compile_definitions(ar_assembly_force_guard_node PRIVATE
  AR_FORCE_GUARD_ROS2)
target_compile_definitions(ar_admittance_joint_6d_node PRIVATE
  XMATEMODEL_LIB_SUPPORTED)

install(TARGETS
  ar_admittance_z_node
  ar_admittance_cartesian_6d_node
  ar_admittance_joint_6d_node
  ar_assembly_force_guard_node
  DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME})
install(PROGRAMS scripts/assembly.sh
  DESTINATION lib/${PROJECT_NAME})

ament_package()
