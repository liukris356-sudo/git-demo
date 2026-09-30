#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$ROOT_DIR/xb7_point_control"
BUILD_DIR="$SOURCE_DIR/build"
RECORD_DIR="${XB7_RECORD_DIR:-$ROOT_DIR/xb7_records}"

ROBOT_IP="${XB7_ROBOT_IP:-192.168.2.160}"
LOCAL_IP="${XB7_LOCAL_IP:-192.168.2.100}"
TOOL_NAME="${XB7_TOOL:-g_tool_1}"
WOBJ_NAME="${XB7_WOBJ:-g_wobj_0}"
SDK_ROOT="${XCORE_SDK_ROOT:-/home/liu/下载/xCoreSDK-v0.7.1.ar_6}"

RECORDER="$BUILD_DIR/xb7_point_recorder"
PLAYER="$BUILD_DIR/xb7_point_player"
FRAME_INSPECTOR="$BUILD_DIR/xb7_frame_inspector"

print_config() {
  cat <<EOF
XB7 point tool configuration
  Robot IP : $ROBOT_IP
  Local IP : $LOCAL_IP
  Tool     : $TOOL_NAME
  Workobj  : $WOBJ_NAME
  SDK root : $SDK_ROOT
  Records  : $RECORD_DIR
EOF
}

usage() {
  cat <<'EOF'
Usage:
  ./xb7_points.sh record [OUTPUT.csv]
  ./xb7_points.sh plan POINTS.csv
  ./xb7_points.sh check POINTS.csv
  ./xb7_points.sh go POINTS.csv POINT_NAME [JOINT_SPEED_RATIO] [MAX_DELTA_DEG]
  ./xb7_points.sh run POINTS.csv [LINEAR_MM_S] [ROTATION_DEG_S]
  ./xb7_points.sh build
  ./xb7_points.sh config
  ./xb7_points.sh frames

Most common first command:
  ./xb7_points.sh record

Inside the recorder:
  CURRENT   print current XB7 pose without saving
  P_SAFE    save the current pose as P_SAFE
  LIST      list saved point names
  UNDO      remove the last point
  QUIT      exit

Optional environment overrides:
  XB7_ROBOT_IP=192.168.2.160
  XB7_LOCAL_IP=192.168.2.100
  XB7_TOOL=g_tool_1
  XB7_WOBJ=g_wobj_0
  XCORE_SDK_ROOT=/path/to/complete/xCoreSDK
EOF
}

build_tools() {
  if [[ ! -f "$SDK_ROOT/include/rokae/robot.h" ]]; then
    echo "ERROR: xCoreSDK header not found: $SDK_ROOT/include/rokae/robot.h" >&2
    exit 1
  fi

  cmake -S "$SOURCE_DIR" -B "$BUILD_DIR" \
    -DXCORE_SDK_ROOT="$SDK_ROOT" \
    -DCMAKE_BUILD_TYPE=Release
  cmake --build "$BUILD_DIR" -j"$(nproc)"
}

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "ERROR: point file not found: $path" >&2
    exit 2
  fi
}

command="${1:-}"
case "$command" in
  config)
    print_config
    ;;

  frames)
    print_config
    build_tools
    exec "$FRAME_INSPECTOR" "$ROBOT_IP" "$LOCAL_IP" "$TOOL_NAME" "$WOBJ_NAME"
    ;;

  build)
    print_config
    build_tools
    echo "XB7 point tools built successfully."
    ;;

  record)
    print_config
    echo
    echo "IMPORTANT: confirm RobotAssist currently uses:"
    echo "  tool=$TOOL_NAME, workobject=$WOBJ_NAME"
    echo "This recorder is read-only: it never powers or moves XB7."
    echo
    build_tools
    mkdir -p "$RECORD_DIR"
    output="${2:-$RECORD_DIR/xb7_points_$(date +%Y%m%d_%H%M%S).csv}"
    echo
    echo "Output file: $output"
    exec "$RECORDER" \
      "$ROBOT_IP" "$LOCAL_IP" "$TOOL_NAME" "$WOBJ_NAME" "$output"
    ;;

  plan)
    if [[ $# -ne 2 ]]; then
      usage
      exit 2
    fi
    require_file "$2"
    build_tools
    exec "$PLAYER" PLAN "$2"
    ;;

  check)
    if [[ $# -ne 2 ]]; then
      usage
      exit 2
    fi
    require_file "$2"
    build_tools
    exec "$PLAYER" CHECK "$ROBOT_IP" "$LOCAL_IP" "$2"
    ;;

  go)
    if [[ $# -lt 3 || $# -gt 5 ]]; then
      usage
      exit 2
    fi
    require_file "$2"
    build_tools
    args=(GO "$ROBOT_IP" "$LOCAL_IP" "$2" "$3")
    if [[ $# -ge 4 ]]; then args+=("$4"); fi
    if [[ $# -ge 5 ]]; then args+=("$5"); fi
    exec "$PLAYER" "${args[@]}"
    ;;

  run)
    if [[ $# -lt 2 || $# -gt 4 ]]; then
      usage
      exit 2
    fi
    require_file "$2"
    build_tools
    args=(RUN "$ROBOT_IP" "$LOCAL_IP" "$2")
    if [[ $# -ge 3 ]]; then args+=("$3"); fi
    if [[ $# -ge 4 ]]; then args+=("$4"); fi
    exec "$PLAYER" "${args[@]}"
    ;;

  help|-h|--help|"")
    usage
    ;;

  *)
    echo "ERROR: unknown command: $command" >&2
    usage
    exit 2
    ;;
esac
