#!/usr/bin/env bash

# AR5 phone-board assembly command wrapper.
# This script intentionally does not use `set -u`: ROS setup scripts can read
# optional, unset environment variables.
set -Eeo pipefail

PROJECT_ROOT="${AR_ASSEMBLY_ROOT:-$HOME/projects/AR5-R-control-demos}"
PROGRAM="$PROJECT_ROOT/build/bin/ar_four_point_smooth_trajectory"
POINTS_FILE="$PROJECT_ROOT/records/assembly_points_leader_01.csv"

ROBOT_IP="${AR_ROBOT_IP:-192.168.2.160}"
LOCAL_IP="${AR_LOCAL_IP:-192.168.2.100}"
TOOL="${AR_TOOL:-g_tool_1}"
WORKOBJECT="${AR_WORKOBJECT:-g_wobj_0}"

FORWARD_LINEAR_MM_S="${AR_FORWARD_LINEAR_MM_S:-1.0}"
FORWARD_ROTATION_DEG_S="${AR_FORWARD_ROTATION_DEG_S:-1.0}"
REVERSE_LINEAR_MM_S="${AR_REVERSE_LINEAR_MM_S:-0.2}"
REVERSE_ROTATION_DEG_S="${AR_REVERSE_ROTATION_DEG_S:-0.2}"

usage() {
  cat <<'EOF'
用法：~/assembly.sh 命令

轨迹命令：
  compile       编译轨迹程序
  plan          只检查正向装配轨迹，不运动
  safe          关节空间回到新的 P_SAFE/p6（路径不避障）
  insert-test   从 P_SAFE 运行到 P_EDGE_IN，停止在斜插点
  assemble      从 P_SAFE 完整装配到 p8

反向拔出命令：
  reverse-plan  只检查完整倒序轨迹，不运动
  release       第1段：p8 慢速解除按压，停止在 P_EDGE_IN
  extract       第2段：从 P_EDGE_IN 慢速退出到 P_SAFE/p6
  reverse       从 p8 一次完成整个反向拔出（首次不建议）

六维力界面：
  force-driver  只启动传感器驱动（保护装配前先在一个终端运行）
  force         启动传感器驱动和曲线窗口
  plot          只启动曲线窗口；传感器驱动已运行时使用
  force-files   查看最近保存的 CSV

力保护装配（阶段2，不含导纳）：
  guard-test      5 N软停/8 N硬停的首次验证
  guard-assemble  27 N软停/30 N硬停，从当前位置回P_SAFE后完整装配
  guard-status    查看 /assembly/force_guard/status

其他：
  check         显示当前程序、点文件、IP和话题状态
  help          显示本帮助

推荐顺序：
  ~/assembly.sh compile
  ~/assembly.sh plan
  ~/assembly.sh safe
  ~/assembly.sh assemble

首次拔出推荐分段：
  ~/assembly.sh reverse-plan
  ~/assembly.sh release
  ~/assembly.sh extract
EOF
}

require_trajectory_files() {
  if [[ ! -x "$PROGRAM" ]]; then
    echo "错误：找不到可执行程序：$PROGRAM" >&2
    echo "请先执行：$0 compile" >&2
    exit 2
  fi
  if [[ ! -f "$POINTS_FILE" ]]; then
    echo "错误：找不到点文件：$POINTS_FILE" >&2
    exit 2
  fi
}

run_trajectory() {
  local mode="$1"
  local linear_speed="$2"
  local rotation_speed="$3"
  require_trajectory_files
  cd "$PROJECT_ROOT"
  exec "$PROGRAM" \
    "$ROBOT_IP" \
    "$LOCAL_IP" \
    "$TOOL" \
    "$WORKOBJECT" \
    "$POINTS_FILE" \
    "$mode" \
    "$linear_speed" \
    "$rotation_speed"
}

source_ros() {
  # shellcheck disable=SC1091
  source /opt/ros/jazzy/setup.bash
  # shellcheck disable=SC1091
  source "$HOME/admittance_ws/install/setup.bash"
}

run_guarded_assembly() {
  local commissioning="$1"
  source_ros

  if [[ ! -f "$POINTS_FILE" ]]; then
    echo "错误：找不到点文件：$POINTS_FILE" >&2
    exit 2
  fi

  local params_file
  params_file="$(ros2 pkg prefix --share ar_admittance_control)/config/assembly_force_guard.yaml"
  if [[ ! -f "$params_file" ]]; then
    echo "错误：找不到保护参数：$params_file" >&2
    echo "请先重新编译并 source ~/admittance_ws/install/setup.bash" >&2
    exit 2
  fi

  local overrides=()
  if [[ "$commissioning" == "true" ]]; then
    overrides=(
      -p soft_force_n:=5.0
      -p hard_force_n:=8.0
      -p hard_torque_nm:=0.5
    )
  fi

  exec ros2 run ar_admittance_control \
    ar_assembly_force_guard_node \
    "$ROBOT_IP" \
    "$LOCAL_IP" \
    "$TOOL" \
    "$WORKOBJECT" \
    "$POINTS_FILE" \
    WIDE_AUTO \
    "$FORWARD_LINEAR_MM_S" \
    "$FORWARD_ROTATION_DEG_S" \
    --ros-args \
    --params-file "$params_file" \
    "${overrides[@]}"
}

command_name="${1:-help}"

case "$command_name" in
  compile)
    cd "$PROJECT_ROOT"
    cmake --build build \
      --target ar_four_point_smooth_trajectory \
      -j"$(nproc)"
    ;;
  plan)
    run_trajectory WIDE_PLAN \
      "$FORWARD_LINEAR_MM_S" "$FORWARD_ROTATION_DEG_S"
    ;;
  safe)
    run_trajectory GO_SAFE \
      "$FORWARD_LINEAR_MM_S" "$FORWARD_ROTATION_DEG_S"
    ;;
  insert-test)
    run_trajectory WIDE_TEST \
      "$FORWARD_LINEAR_MM_S" "$FORWARD_ROTATION_DEG_S"
    ;;
  assemble)
    run_trajectory WIDE_RUN \
      "$FORWARD_LINEAR_MM_S" "$FORWARD_ROTATION_DEG_S"
    ;;
  reverse-plan)
    run_trajectory WIDE_REVERSE_PLAN \
      "$REVERSE_LINEAR_MM_S" "$REVERSE_ROTATION_DEG_S"
    ;;
  release)
    run_trajectory WIDE_REVERSE_TEST \
      "$REVERSE_LINEAR_MM_S" "$REVERSE_ROTATION_DEG_S"
    ;;
  extract)
    run_trajectory WIDE_REVERSE_EXTRACT \
      "$REVERSE_LINEAR_MM_S" "$REVERSE_ROTATION_DEG_S"
    ;;
  reverse)
    run_trajectory WIDE_REVERSE_RUN \
      "$REVERSE_LINEAR_MM_S" "$REVERSE_ROTATION_DEG_S"
    ;;
  force-driver)
    source_ros
    exec ros2 run force_sensor_yl force_sensor_yl_node --ros-args \
      -p port:=/dev/ttyUSB0 \
      -p topic_name:=/m3815/wrench_raw
    ;;
  force)
    source_ros
    exec ros2 launch force_sensor_yl monitor.launch.py \
      port:=/dev/ttyUSB0 \
      topic_name:=/m3815/wrench_raw
    ;;
  plot)
    source_ros
    exec ros2 run force_sensor_yl force_sensor_yl_monitor --ros-args \
      -p topic_name:=/m3815/wrench_raw
    ;;
  force-files)
    mkdir -p "$HOME/force_sensor_logs"
    ls -lht "$HOME/force_sensor_logs"
    ;;
  guard-test)
    run_guarded_assembly true
    ;;
  guard-assemble)
    run_guarded_assembly false
    ;;
  guard-status)
    source_ros
    exec ros2 topic echo /assembly/force_guard/status \
      --qos-durability transient_local
    ;;
  check)
    echo "程序：$PROGRAM"
    echo "点文件：$POINTS_FILE"
    echo "机器人/本机：$ROBOT_IP / $LOCAL_IP"
    echo "工具/工件：$TOOL / $WORKOBJECT"
    [[ -x "$PROGRAM" ]] && echo "程序状态：存在" || echo "程序状态：缺失"
    [[ -f "$POINTS_FILE" ]] && echo "点文件状态：存在" || echo "点文件状态：缺失"
    if command -v ping >/dev/null 2>&1; then
      ping -c 1 -W 1 "$ROBOT_IP" >/dev/null 2>&1 \
        && echo "机器人网络：可达" \
        || echo "机器人网络：不可达"
    fi
    if [[ -e /dev/ttyUSB0 ]]; then
      echo "六维力串口：/dev/ttyUSB0 存在"
    else
      echo "六维力串口：/dev/ttyUSB0 不存在"
    fi
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "未知命令：$command_name" >&2
    usage
    exit 2
    ;;
esac
