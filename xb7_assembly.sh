#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$ROOT_DIR/xb7_point_control/build"
PLAYER="$BUILD_DIR/xb7_point_player"
ROBOT_IP="${XB7_ROBOT_IP:-192.168.2.160}"
LOCAL_IP="${XB7_LOCAL_IP:-192.168.2.100}"

FULL="$ROOT_DIR/xb7_records/xb7_assembly_new_full_20260929.csv"
INSERT="$ROOT_DIR/xb7_records/xb7_assembly_new_insert_20260929.csv"
CLEARANCE="$ROOT_DIR/xb7_records/xb7_assembly_new_clearance_20260929.csv"
PRESS="$ROOT_DIR/xb7_records/xb7_assembly_new_press_20260929.csv"
REVERSE_FULL="$ROOT_DIR/xb7_records/xb7_assembly_new_reverse_full_20260929.csv"
REVERSE_RELEASE="$ROOT_DIR/xb7_records/xb7_assembly_new_reverse_release_20260929.csv"
REVERSE_EXTRACT="$ROOT_DIR/xb7_records/xb7_assembly_new_reverse_extract_20260929.csv"
SAFETY_LOCK="$ROOT_DIR/xb7_records/SAFETY_LOCK_AXIS5_35610.txt"

usage() {
  cat <<'EOF'
XB7 无力控示教装配轨迹（g_tool_1 / g_wobj_0，2026-09-29新点位：safe -> pxiecha2 -> pbijing1 -> pfinal4）

Usage:
  ./xb7_assembly.sh plan            # 打印轨迹点位与速度计划，不连接机器人
  ./xb7_assembly.sh check           # 机械臂控制器 checkPath，不上电、不运动
  ./xb7_assembly.sh go-safe         # 0.5%关节速度回P_SAFE_NEW
  ./xb7_assembly.sh insert-test     # 从安全点到斜插点 pxiecha2 (2点，平稳进给)
  ./xb7_assembly.sh clearance-test  # 从斜插点 pxiecha2 到逼近点 pbijing1 (2点，低速贴合)
  ./xb7_assembly.sh press-test      # 从逼近点 pbijing1 到最终点 pfinal4 (2点，微速按压到位)
  ./xb7_assembly.sh reverse-plan    # 只打印完整倒序轨迹
  ./xb7_assembly.sh reverse-check   # 检查完整倒序轨迹，不运动
  ./xb7_assembly.sh reverse-release # 最终点微速反向释放到 pbijing1 (2点)
  ./xb7_assembly.sh reverse-extract # 从 pbijing1 反向退回到 P_SAFE_NEW (3点)
  ./xb7_assembly.sh reverse-test    # 完整 4 点原路倒序退回安全点 (4点)
  ./xb7_assembly.sh full-test [V]   # 全流程连续执行：P_SAFE_NEW -> pxiecha2 -> pbijing1 -> pfinal4 (4点，平稳低速)
  ./xb7_assembly.sh full [V]        # full-test 的简写
  ./xb7_assembly.sh shadow          # 【六维导纳控制】只读安全校验模式（自动转发到 xb7_admittance.sh）
  ./xb7_assembly.sh run             # 【六维导纳控制】实机上电自适应装配（自动转发到 xb7_admittance.sh）

点位顺序：P_SAFE_NEW -> pxiecha2 -> pbijing1 -> pfinal4 (100%示教原值，无任何偏置)
速度方案：安全点至斜插点平稳进给(0.6 mm/s)，逼近与按压极低速贴合并到位(0.2~0.1 mm/s)，确保顺滑安全。
EOF
}

build() {
  "$ROOT_DIR/xb7_points.sh" build >/dev/null
}

require_motion_unlocked() {
  if [[ -f "$SAFETY_LOCK" ]]; then
    echo "MOTION DISABLED: Axis 5 torque fault 35610 / 0xFF81 was reported." >&2
    echo "Recover manually and review the interference before removing:" >&2
    echo "  $SAFETY_LOCK" >&2
    exit 3
  fi
}

for file in "$FULL" "$INSERT" "$CLEARANCE" "$PRESS" \
            "$REVERSE_FULL" "$REVERSE_RELEASE" "$REVERSE_EXTRACT"; do
  if [[ ! -f "$file" ]]; then
    echo "ERROR: missing point file: $file" >&2
    exit 2
  fi
done

case "${1:-}" in
  plan)
    build
    exec "$PLAYER" PLAN "$FULL"
    ;;
  check)
    build
    exec "$PLAYER" CHECK "$ROBOT_IP" "$LOCAL_IP" "$FULL"
    ;;
  go-safe)
    require_motion_unlocked
    build
    target_name="P_SAFE"
    if grep -q "^P_SAFE_NEW," "$FULL"; then
      target_name="P_SAFE_NEW"
    fi
    exec "$PLAYER" GO "$ROBOT_IP" "$LOCAL_IP" "$FULL" "$target_name" 0.005 30
    ;;
  insert-test)
    require_motion_unlocked
    echo "Executing INSERT stage: P_SAFE_NEW -> pxiecha2."
    echo "Robot must already be at P_SAFE_NEW; keep E-stop reachable."
    build
    exec "$PLAYER" RUN "$ROBOT_IP" "$LOCAL_IP" "$INSERT"
    ;;
  clearance-test)
    require_motion_unlocked
    echo "Executing CLEARANCE/APPROACH stage: pxiecha2 -> pbijing1."
    echo "Robot must already be at pxiecha2; keep E-stop reachable."
    build
    exec "$PLAYER" RUN "$ROBOT_IP" "$LOCAL_IP" "$CLEARANCE"
    ;;
  press-test)
    require_motion_unlocked
    echo "Executing PRESS stage: pbijing1 -> pfinal4."
    echo "Final World X=615.966mm, Y=2.891mm, Z=-7.598mm."
    echo "Run only after clearance-test is physically verified."
    build
    exec "$PLAYER" RUN "$ROBOT_IP" "$LOCAL_IP" "$PRESS"
    ;;
  reverse-plan)
    build
    exec "$PLAYER" PLAN "$REVERSE_FULL"
    ;;
  reverse-check)
    build
    exec "$PLAYER" CHECK "$ROBOT_IP" "$LOCAL_IP" "$REVERSE_FULL"
    ;;
  reverse-release)
    require_motion_unlocked
    echo "Executing reverse release: pfinal4 -> pbijing1."
    echo "Robot must already match pfinal4."
    build
    exec "$PLAYER" RUN "$ROBOT_IP" "$LOCAL_IP" "$REVERSE_RELEASE"
    ;;
  reverse-extract)
    require_motion_unlocked
    echo "Executing reverse extraction: pbijing1 -> pxiecha2 -> P_SAFE_NEW."
    echo "Robot must already match pbijing1."
    build
    exec "$PLAYER" RUN "$ROBOT_IP" "$LOCAL_IP" "$REVERSE_EXTRACT"
    ;;
  reverse-test)
    require_motion_unlocked
    echo "Executing complete reverse extraction: pfinal4 -> pbijing1 -> pxiecha2 -> P_SAFE_NEW (4 points)."
    echo "This is position-controlled extraction, not force-regulated pulling."
    build
    exec "$PLAYER" RUN "$ROBOT_IP" "$LOCAL_IP" "$REVERSE_FULL"
    ;;
  full-test|full|run)
    require_motion_unlocked
    echo "WARNING: no force control; executing FULL assembly sequence from P_SAFE_NEW to pfinal4."
    echo "Points: P_SAFE_NEW -> pxiecha2 -> pbijing1 -> pfinal4"
    echo "Robot must already be at P_SAFE_NEW; keep E-stop reachable."
    build
    speed="${2:-}"
    rot_speed="${3:-}"
    if [[ -n "$speed" ]]; then
      echo "Overriding full trajectory speed: linear_speed=${speed} mm/s, rot_speed=${rot_speed:-$speed} deg/s"
      exec "$PLAYER" RUN "$ROBOT_IP" "$LOCAL_IP" "$FULL" "$speed" "${rot_speed:-$speed}"
    else
      echo "Executing safe & smooth assembly trajectory (Safe->Insert: 0.6mm/s, Approach: 0.2mm/s, Final: 0.1mm/s)."
      exec "$PLAYER" RUN "$ROBOT_IP" "$LOCAL_IP" "$FULL"
    fi
    ;;
  shadow|admittance-shadow)
    exec "$ROOT_DIR/xb7_admittance.sh" shadow "${@:2}"
    ;;
  run|admittance-run)
    exec "$ROOT_DIR/xb7_admittance.sh" run "${@:2}"
    ;;
  help|-h|--help|"")
    usage
    ;;
  *)
    echo "ERROR: unknown command: $1" >&2
    usage
    exit 2
    ;;
esac
