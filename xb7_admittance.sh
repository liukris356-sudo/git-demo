#!/usr/bin/env bash
set -eo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROBOT_IP="${XB7_ROBOT_IP:-192.168.2.160}"
LOCAL_IP="${XB7_LOCAL_IP:-192.168.2.100}"
SDK_ROOT="${XCORE_SDK_ROOT:-/home/liu/下载/xCoreSDK-v0.7.1.ar_6}"

usage() {
  cat <<'EOF'
XB7 机械臂六维笛卡尔导纳装配控制工具（TA67L 力传感器 + 阶段正常力包络）

用法:
  ./xb7_admittance.sh build       # 编译 ROS 2 导纳包与传感器驱动
  ./xb7_admittance.sh status      # 检查机械臂网络连接和力传感器话题
  ./xb7_admittance.sh shadow      # 【推荐首选】只读模式：不上电不运动，校验力正负号与导纳位姿输出
  ./xb7_admittance.sh run         # 【上电实机】执行带六维导纳闭环的真实装配（需严格手持急停）
  ./xb7_admittance.sh help        # 查看本帮助

操作安全流程：
  1. 先在一个终端启动力传感器驱动：
     source install/setup.bash
     ros2 launch force_sensor_ta67l monitor.launch.py port:=/dev/serial/by-id/...
  2. 运行 ./xb7_admittance.sh status 确认 /ta67l/wrench_raw 话题正常发布
  3. 运行 ./xb7_admittance.sh shadow，用手轻推传感器，观察终端输出的力与 OffsetXYZ 是否符合物理方向
  4. 确认所有轴符号无误后，手持急停，再执行 ./xb7_admittance.sh run
EOF
}

build() {
  echo "Building force_sensor_ta67l and ar_admittance_control..."
  source /opt/ros/jazzy/setup.bash
  colcon build \
    --base-paths ./force_sensor_ta67l ./ar_admittance_control \
    --symlink-install \
    --packages-select force_sensor_ta67l ar_admittance_control \
    --cmake-args -DXCORE_SDK_ROOT="$SDK_ROOT"
  echo "Build finished successfully."
}

check_status() {
  source /opt/ros/jazzy/setup.bash
  if [[ -f "$ROOT_DIR/install/setup.bash" ]]; then
    source "$ROOT_DIR/install/setup.bash"
  fi

  echo "=== 1. 检查机械臂网络连接 ($ROBOT_IP) ==="
  if ping -c 1 -W 1 "$ROBOT_IP" >/dev/null 2>&1; then
    echo "  [OK] 成功 ping 通机械臂控制器: $ROBOT_IP"
  else
    echo "  [FAIL] 无法连接机械臂 $ROBOT_IP，请检查网线及本机 IP ($LOCAL_IP) 设置"
  fi

  echo "=== 2. 检查力传感器话题 (/ta67l/wrench_raw) ==="
  if ros2 topic list 2>/dev/null | grep -q "^/ta67l/wrench_raw$"; then
    echo "  [OK] 话题 /ta67l/wrench_raw 存在，正在采样 2 秒评估频率..."
    ros2 topic hz /ta67l/wrench_raw --window 25 2>/dev/null | head -n 3 || true
  else
    echo "  [WARN] 话题 /ta67l/wrench_raw 不存在。"
    echo "         请先启动传感器驱动：ros2 launch force_sensor_ta67l monitor.launch.py"
  fi
}

run_shadow() {
  source /opt/ros/jazzy/setup.bash
  source "$ROOT_DIR/install/setup.bash"
  export XB7_ROBOT_IP="$ROBOT_IP"
  export XB7_LOCAL_IP="$LOCAL_IP"
  echo "Starting XB7 6D Admittance in SHADOW mode (read-only safe test)..."
  ros2 launch ar_admittance_control xb7_assembly_cartesian_6d_admittance.launch.py active_control:=false
}

run_active() {
  source /opt/ros/jazzy/setup.bash
  source "$ROOT_DIR/install/setup.bash"
  export XB7_ROBOT_IP="$ROBOT_IP"
  export XB7_LOCAL_IP="$LOCAL_IP"
  echo "WARNING: Starting XB7 6D Admittance in ACTIVE mode!"
  echo "Ensure workspace is clear and hold E-STOP switch!"
  ros2 launch ar_admittance_control xb7_assembly_cartesian_6d_admittance.launch.py active_control:=true
}

case "${1:-}" in
  build)
    build
    ;;
  status)
    check_status
    ;;
  shadow)
    run_shadow
    ;;
  run)
    run_active
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage
    exit 1
    ;;
esac
