#!/usr/bin/env bash
set -eo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$ROOT_DIR/xb7_point_control/build"
PLAYER="$BUILD_DIR/xb7_point_player"
ROBOT_IP="${XB7_ROBOT_IP:-192.168.2.160}"
LOCAL_IP="${XB7_LOCAL_IP:-192.168.2.100}"

FORWARD_FILE="$ROOT_DIR/xb7_records/tcl_assembly_forward.csv"
REVERSE_FILE="$ROOT_DIR/xb7_records/tcl_assembly_reverse.csv"
CYCLE_FILE="$ROOT_DIR/xb7_records/tcl_assembly_cycle.csv"

# 默认演示速度方案
DEFAULT_FORWARD_SPEED="2.5"
DEFAULT_REVERSE_SPEED="3.5"
DEFAULT_ROT_SPEED="1.0"       # deg/s

usage() {
  cat <<'HELP'
======================================================================
  XB7 机器人 - TCL 主板三点门字形快速位置控制演示程序
  轨迹路线: psafenewtcl (高空安全点) -> pmiddle (插装上方对准) -> ptclfinalnew1 (装配到位)
======================================================================

用法:
  ./tcl_demo.sh auto [SPEED] [-y]   # 【推荐】一键连贯全自动：自动回安全点 -> 紧接着执行插装
  ./tcl_demo.sh cycle [SPEED] [-y]  # 【一镜到底】往复全闭环连续：安全点 -> 插装到位 -> 垂直拔出回安全点 (无停顿连续轨迹)
  ./tcl_demo.sh run [SPEED] [-y]    # 单独执行装配前进：psafenewtcl -> pmiddle -> ptclfinalnew1
  ./tcl_demo.sh retract [SPEED] [-y]# 单独执行反向退出：ptclfinalnew1 -> pmiddle -> psafenewtcl
  ./tcl_demo.sh go-safe [-y]        # 慢速平稳移动到安全点 psafenewtcl
  ./tcl_demo.sh plan                # 打印所有正反向、往复闭环轨迹计划，不连机
  ./tcl_demo.sh check               # 控制器 checkPath 校验所有路径，不上电、不动作
  ./tcl_demo.sh help                # 查看本帮助

速度说明：
  - 默认使用分段速度优化（高空平移 4.0~5.0 mm/s，垂直插拔 2.5~3.5 mm/s）
  - 可传 SPEED 参数覆盖（如 ./tcl_demo.sh auto 5 -y 以 5mm/s 运行）
======================================================================
HELP
}

build_if_needed() {
  if [[ ! -x "$PLAYER" ]]; then
    echo "Building xb7_point_player..."
    "$ROOT_DIR/xb7_points.sh" build >/dev/null
  fi
}

cmd_plan() {
  build_if_needed
  echo "=== 1. 正向三点轨迹计划 (psafenewtcl -> pmiddle -> ptclfinalnew1) ==="
  "$PLAYER" PLAN "$FORWARD_FILE"
  echo ""
  echo "=== 2. 反向三点退出计划 (ptclfinalnew1 -> pmiddle -> psafenewtcl) ==="
  "$PLAYER" PLAN "$REVERSE_FILE"
  echo ""
  echo "=== 3. 往复全闭环连续轨迹 (psafenewtcl -> pmiddle -> ptclfinalnew1 -> pmiddle -> psafenewtcl) ==="
  "$PLAYER" PLAN "$CYCLE_FILE"
}

cmd_check() {
  build_if_needed
  echo "=== 1. 检查正向轨迹 (psafenewtcl -> pmiddle -> ptclfinalnew1) ==="
  "$PLAYER" CHECK "$ROBOT_IP" "$LOCAL_IP" "$FORWARD_FILE"
  echo ""
  echo "=== 2. 检查反向轨迹 (ptclfinalnew1 -> pmiddle -> psafenewtcl) ==="
  "$PLAYER" CHECK "$ROBOT_IP" "$LOCAL_IP" "$REVERSE_FILE"
  echo ""
  echo "=== 3. 检查往复闭环连续轨迹 ==="
  "$PLAYER" CHECK "$ROBOT_IP" "$LOCAL_IP" "$CYCLE_FILE"
}

cmd_go_safe() {
  build_if_needed
  local auto_confirm=false
  for arg in "$@"; do
    if [[ "$arg" == "-y" || "$arg" == "--yes" ]]; then
      auto_confirm=true
    fi
  done
  local safe_point
  safe_point=$(grep -v "^#" "$FORWARD_FILE" | grep -v "^name" | head -n 1 | cut -d',' -f1)
  echo "Moving robot to safe point ($safe_point) at 1% joint speed..."
  if $auto_confirm; then
    echo "ARM_XB7_GO" | "$PLAYER" GO "$ROBOT_IP" "$LOCAL_IP" "$FORWARD_FILE" "$safe_point" 0.01 45
  else
    "$PLAYER" GO "$ROBOT_IP" "$LOCAL_IP" "$FORWARD_FILE" "$safe_point" 0.01 45
  fi
}

cmd_run() {
  build_if_needed
  local speed=""
  local auto_confirm=false
  for arg in "$@"; do
    if [[ "$arg" == "-y" || "$arg" == "--yes" ]]; then
      auto_confirm=true
    elif [[ "$arg" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
      speed="$arg"
    fi
  done

  local speed_args=()
  if [[ -n "$speed" ]]; then
    echo "Executing TCL forward motion with speed override: ${speed} mm/s..."
    speed_args=("$speed" "$DEFAULT_ROT_SPEED")
  else
    echo "Executing TCL forward motion with planned segment speeds (pmiddle: 4.0 mm/s, ptclfinalnew1: 2.5 mm/s)..."
  fi

  if $auto_confirm; then
    echo "ARM_XB7_RUN" | "$PLAYER" RUN "$ROBOT_IP" "$LOCAL_IP" "$FORWARD_FILE" "${speed_args[@]}"
  else
    "$PLAYER" RUN "$ROBOT_IP" "$LOCAL_IP" "$FORWARD_FILE" "${speed_args[@]}"
  fi
}

cmd_retract() {
  build_if_needed
  local speed=""
  local auto_confirm=false
  for arg in "$@"; do
    if [[ "$arg" == "-y" || "$arg" == "--yes" ]]; then
      auto_confirm=true
    elif [[ "$arg" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
      speed="$arg"
    fi
  done

  local speed_args=()
  if [[ -n "$speed" ]]; then
    echo "Executing TCL retract motion with speed override: ${speed} mm/s..."
    speed_args=("$speed" "$DEFAULT_ROT_SPEED")
  else
    echo "Executing TCL retract motion with planned segment speeds (pmiddle: 3.5 mm/s, psafenewtcl: 5.0 mm/s)..."
  fi

  if $auto_confirm; then
    echo "ARM_XB7_RUN" | "$PLAYER" RUN "$ROBOT_IP" "$LOCAL_IP" "$REVERSE_FILE" "${speed_args[@]}"
  else
    "$PLAYER" RUN "$ROBOT_IP" "$LOCAL_IP" "$REVERSE_FILE" "${speed_args[@]}"
  fi
}

cmd_auto() {
  build_if_needed
  local speed=""
  local auto_confirm=false
  for arg in "$@"; do
    if [[ "$arg" == "-y" || "$arg" == "--yes" ]]; then
      auto_confirm=true
    elif [[ "$arg" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
      speed="$arg"
    fi
  done

  echo "========================================================"
  echo "  一键连续执行: [1] 自动回安全点 -> [2] 连续门字形装配"
  echo "========================================================"
  local safe_point
  safe_point=$(grep -v "^#" "$FORWARD_FILE" | grep -v "^name" | head -n 1 | cut -d',' -f1)

  echo ">>> [步骤 1/2] 移动机器人至起始安全点 ($safe_point)..."
  if $auto_confirm; then
    echo "ARM_XB7_GO" | "$PLAYER" GO "$ROBOT_IP" "$LOCAL_IP" "$FORWARD_FILE" "$safe_point" 0.01 45
  else
    "$PLAYER" GO "$ROBOT_IP" "$LOCAL_IP" "$FORWARD_FILE" "$safe_point" 0.01 45
  fi

  echo ">>> 等待机械臂电源与通信状态复位 (2秒)..."
  sleep 2

  echo ""
  echo ">>> [步骤 2/2] 启动装配前进 (psafenewtcl -> pmiddle -> ptclfinalnew1)..."
  local speed_args=()
  if [[ -n "$speed" ]]; then
    speed_args=("$speed" "$DEFAULT_ROT_SPEED")
  fi

  if $auto_confirm; then
    echo "ARM_XB7_RUN" | "$PLAYER" RUN "$ROBOT_IP" "$LOCAL_IP" "$FORWARD_FILE" "${speed_args[@]}"
  else
    "$PLAYER" RUN "$ROBOT_IP" "$LOCAL_IP" "$FORWARD_FILE" "${speed_args[@]}"
  fi

  echo ">>> 一键全流程装配完成！"
}

cmd_cycle() {
  build_if_needed
  local speed=""
  local auto_confirm=false
  for arg in "$@"; do
    if [[ "$arg" == "-y" || "$arg" == "--yes" ]]; then
      auto_confirm=true
    elif [[ "$arg" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
      speed="$arg"
    fi
  done

  echo "========================================================"
  echo "  一镜到底全闭环连续演示 (装配进给 + 垂直拔出回安全点 无缝连续):"
  echo "  路线: psafenewtcl -> pmiddle -> ptclfinalnew1 -> pmiddle -> psafenewtcl"
  echo "========================================================"

  # 1. 确保在安全点
  local safe_point
  safe_point=$(grep -v "^#" "$FORWARD_FILE" | grep -v "^name" | head -n 1 | cut -d',' -f1)
  echo ">>> [准备步骤] 确认/回到起始安全点 ($safe_point)..."
  if $auto_confirm; then
    echo "ARM_XB7_GO" | "$PLAYER" GO "$ROBOT_IP" "$LOCAL_IP" "$FORWARD_FILE" "$safe_point" 0.01 45
  else
    "$PLAYER" GO "$ROBOT_IP" "$LOCAL_IP" "$FORWARD_FILE" "$safe_point" 0.01 45
  fi

  local speed_args=()
  if [[ -n "$speed" ]]; then
    echo "Executing continuous cycle with speed override: ${speed} mm/s..."
    speed_args=("$speed" "$DEFAULT_ROT_SPEED")
  else
    echo "Executing continuous cycle with planned segment speeds (4段插补单次连续执行)..."
  fi

  echo ">>> [闭环执行] 启动全连续往复轨迹..."
  if $auto_confirm; then
    echo "ARM_XB7_RUN" | "$PLAYER" RUN "$ROBOT_IP" "$LOCAL_IP" "$CYCLE_FILE" "${speed_args[@]}"
  else
    "$PLAYER" RUN "$ROBOT_IP" "$LOCAL_IP" "$CYCLE_FILE" "${speed_args[@]}"
  fi

  echo ">>> 往复全闭环连续演示成功完成！"
}

case "${1:-}" in
  plan)
    cmd_plan
    ;;
  check)
    cmd_check
    ;;
  go-safe|safe)
    shift
    cmd_go_safe "$@"
    ;;
  run|forward)
    shift
    cmd_run "$@"
    ;;
  retract|reverse|return)
    shift
    cmd_retract "$@"
    ;;
  auto|start)
    shift
    cmd_auto "$@"
    ;;
  cycle|demo)
    shift
    cmd_cycle "$@"
    ;;
  help|-h|--help|"")
    usage
    ;;
  *)
    echo "Unknown command: $1" >&2
    usage
    exit 2
    ;;
esac
