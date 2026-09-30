#!/usr/bin/env python3
"""Render a spacious long-form AR5 6D admittance control flowchart."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon
from PIL import Image


OUT = Path("analysis_output/ar5_admittance_algorithm_flowchart_long.png")
PART1 = Path("analysis_output/ar5_admittance_algorithm_flowchart_part1.png")
PART2 = Path("analysis_output/ar5_admittance_algorithm_flowchart_part2.png")


def box(ax, x, y, w, h, title, detail="", edge="#1976D2", fill="#EDF5FB"):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.012,rounding_size=0.013",
        linewidth=2.0, edgecolor=edge, facecolor=fill,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h * 0.66, title, ha="center", va="center", fontsize=14.5, weight="bold", color="#1F3342")
    if detail:
        ax.text(x + w / 2, y + h * 0.30, detail, ha="center", va="center", fontsize=11.2, color="#4F6574")
    return patch


def decision(ax, cx, cy, w, h, text):
    points = [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)]
    patch = Polygon(points, closed=True, linewidth=2.0, edgecolor="#E65100", facecolor="#FFF4E8")
    ax.add_patch(patch)
    ax.text(cx, cy, text, ha="center", va="center", fontsize=12.5, weight="bold", color="#6D3B13")
    return patch


def arrow(ax, start, end, color="#526675", text=None, text_offset=(0, 0), dashed=False, head=True):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>" if head else "-",
            mutation_scale=16,
            linewidth=1.8,
            linestyle="--" if dashed else "-",
            color=color,
        )
    )
    if text:
        ax.text(
            (start[0] + end[0]) / 2 + text_offset[0],
            (start[1] + end[1]) / 2 + text_offset[1],
            text,
            fontsize=10.5,
            color=color,
            ha="center",
            va="center",
        )


def main():
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Noto Sans CJK SC", "DejaVu Sans"],
            "axes.unicode_minus": False,
        }
    )
    fig, ax = plt.subplots(figsize=(10, 22), dpi=180)
    fig.patch.set_facecolor("#F6F8FA")
    ax.set_facecolor("#F6F8FA")
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.02, 1)
    ax.axis("off")

    ax.text(0.5, 0.994, "AR5阶段感知六维导纳控制流程", ha="center", va="top", fontsize=22, weight="bold", color="#153247")
    ax.text(0.5, 0.972, "示教轨迹为移动中心 · 异常扳手驱动位姿修正 · 严重接触时暂停轨迹但保持导纳", ha="center", va="top", fontsize=11, color="#526675")

    box(ax, 0.25, 0.918, 0.50, 0.040, "1　启动与参数校验", "加载M/D/K、限幅、包络、阶段掩码和示教点")
    box(ax, 0.25, 0.854, 0.50, 0.040, "2　力传感器清零", "等待新鲜数据；静止2 s tare；检查清零稳定性")
    box(ax, 0.25, 0.790, 0.50, 0.040, "3　上线前安全检查", "P_SAFE、软限位、checkPath、控制权与人工确认")
    arrow(ax, (0.5, 0.918), (0.5, 0.897))
    arrow(ax, (0.5, 0.854), (0.5, 0.833))
    arrow(ax, (0.5, 0.790), (0.5, 0.763))

    ax.text(0.10, 0.750, "1 kHz 实时控制循环", fontsize=13.5, weight="bold", color="#1976D2")
    box(ax, 0.18, 0.700, 0.64, 0.043, "4　采集六维力与机器人状态", "W_raw、tcpPose_m、tcpPose_c、joint、elbow")
    box(ax, 0.18, 0.632, 0.64, 0.043, "5　扳手坐标变换", "清零 → Sensor→Tool外参 → 当前工件/Base参考方向")
    box(ax, 0.18, 0.564, 0.64, 0.043, "6　硬限与数据看门狗", "数据≤50 ms；合力<35 N；合力矩<1.50 N·m")
    box(ax, 0.18, 0.496, 0.64, 0.043, "7　阶段正常力包络", "按进度插值c(s)、h(s)，向零扩展并提取W_excess")
    arrow(ax, (0.5, 0.700), (0.5, 0.679))
    arrow(ax, (0.5, 0.632), (0.5, 0.611))
    arrow(ax, (0.5, 0.564), (0.5, 0.543))
    arrow(ax, (0.5, 0.496), (0.5, 0.468))

    decision(ax, 0.5, 0.440, 0.46, 0.052, "8　扰动预置 / 尚未启动回中？")
    box(ax, 0.04, 0.352, 0.38, 0.052, "平滑建立测试偏差", "五次曲线；预置阶段接触立即停止", edge="#E65100", fill="#FFF4E8")
    box(ax, 0.58, 0.352, 0.38, 0.052, "六维导纳离散求解", "滤波→死区→M/D/K→加速度/速度/位姿限幅", edge="#1976D2", fill="#EDF5FB")
    arrow(ax, (0.27, 0.440), (0.23, 0.407), text="是", text_offset=(-0.012, 0.009))
    arrow(ax, (0.73, 0.440), (0.77, 0.407), text="否", text_offset=(0.012, 0.009))

    decision(ax, 0.5, 0.302, 0.46, 0.052, "9　异常力严重并持续0.10 s？")
    arrow(ax, (0.23, 0.352), (0.39, 0.318))
    arrow(ax, (0.77, 0.352), (0.61, 0.318))
    box(ax, 0.04, 0.210, 0.38, 0.052, "轨迹调节器进入恢复", "rate降至0；名义时间冻结\n导纳继续卸力", edge="#E65100", fill="#FFF4E8")
    box(ax, 0.58, 0.210, 0.38, 0.052, "继续名义轨迹", "小偏差由导纳在线修正\nrate保持1", edge="#2E7D32", fill="#EDF8F0")
    arrow(ax, (0.27, 0.302), (0.23, 0.265), text="是", text_offset=(-0.012, 0.010))
    arrow(ax, (0.73, 0.302), (0.77, 0.265), text="否", text_offset=(0.012, 0.010))

    box(ax, 0.25, 0.142, 0.50, 0.046, "10　位姿合成并输出", "p_cmd=p_nom+Δp；R_cmd=Exp([Δr]×)R_nom")
    arrow(ax, (0.23, 0.210), (0.40, 0.188))
    arrow(ax, (0.77, 0.210), (0.60, 0.188))
    box(ax, 0.25, 0.085, 0.50, 0.040, "11　执行链与跟踪检查", "desired ↔ tcpPose_c ↔ tcpPose_m；饱和与恢复超时")
    arrow(ax, (0.5, 0.142), (0.5, 0.128))
    decision(ax, 0.5, 0.038, 0.34, 0.034, "12　就位、继续或故障？")
    arrow(ax, (0.5, 0.085), (0.5, 0.058))

    box(ax, 0.01, -0.008, 0.25, 0.027, "成功就位", "seat=REACHED", edge="#2E7D32", fill="#EDF8F0")
    box(ax, 0.74, -0.008, 0.25, 0.027, "安全退出", "stop→断网→下电→manual", edge="#C62828", fill="#FDEEEE")
    arrow(ax, (0.33, 0.038), (0.26, 0.012), color="#2E7D32", text="成功", text_offset=(-0.012, 0.010))
    arrow(ax, (0.67, 0.038), (0.74, 0.012), color="#C62828", text="故障", text_offset=(0.012, 0.010))

    ax.text(0.84, 0.074, "未结束：返回实时循环", fontsize=10.5, color="#1976D2", ha="center")
    arrow(ax, (0.64, 0.046), (0.975, 0.072), color="#1976D2", dashed=True, head=False)
    arrow(ax, (0.975, 0.072), (0.975, 0.722), color="#1976D2", dashed=True, head=False)
    arrow(ax, (0.975, 0.722), (0.825, 0.722), color="#1976D2", dashed=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    with Image.open(OUT) as image:
        split = int(image.height * 0.52)
        overlap = int(image.height * 0.025)
        image.crop((0, 0, image.width, min(image.height, split + overlap))).save(PART1)
        image.crop((0, max(0, split - overlap), image.width, image.height)).save(PART2)

    print(OUT.resolve())
    print(PART1.resolve())
    print(PART2.resolve())


if __name__ == "__main__":
    main()
