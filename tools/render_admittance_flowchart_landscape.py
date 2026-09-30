#!/usr/bin/env python3
"""Render a spacious landscape AR5 6D admittance control flowchart."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon


OUT = Path("analysis_output/ar5_admittance_algorithm_flowchart_landscape.png")
BG = "#F6F8FA"
INK = "#1F3342"
MUTED = "#526675"
BLUE = "#1976D2"
ORANGE = "#E65100"
GREEN = "#2E7D32"
RED = "#C62828"


def box(ax, x, y, w, h, title, detail="", edge=BLUE, fill="#EDF5FB"):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.010,rounding_size=0.012",
        linewidth=2.2,
        edgecolor=edge,
        facecolor=fill,
    )
    ax.add_patch(patch)
    title_y = y + (h * 0.65 if detail else h * 0.50)
    ax.text(
        x + w / 2,
        title_y,
        title,
        ha="center",
        va="center",
        fontsize=15.5,
        weight="bold",
        color=INK,
    )
    if detail:
        ax.text(
            x + w / 2,
            y + h * 0.27,
            detail,
            ha="center",
            va="center",
            fontsize=11.7,
            linespacing=1.18,
            color=MUTED,
        )
    return patch


def decision(ax, cx, cy, w, h, text):
    points = [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)]
    patch = Polygon(points, closed=True, linewidth=2.2, edgecolor=ORANGE, facecolor="#FFF4E8")
    ax.add_patch(patch)
    ax.text(cx, cy, text, ha="center", va="center", fontsize=13.2, weight="bold", color="#6D3B13", linespacing=1.18)
    return patch


def arrow(ax, start, end, color=MUTED, text=None, text_offset=(0, 0), dashed=False, head=True):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>" if head else "-",
            mutation_scale=18,
            linewidth=2.0,
            linestyle="--" if dashed else "-",
            color=color,
            shrinkA=0,
            shrinkB=0,
        )
    )
    if text:
        ax.text(
            (start[0] + end[0]) / 2 + text_offset[0],
            (start[1] + end[1]) / 2 + text_offset[1],
            text,
            fontsize=11.5,
            weight="bold",
            color=color,
            ha="center",
            va="center",
            bbox={"boxstyle": "round,pad=0.16", "facecolor": BG, "edgecolor": "none"},
        )


def poly_arrow(ax, points, color=MUTED, text=None, text_xy=None, dashed=False):
    for start, end in zip(points[:-2], points[1:-1]):
        arrow(ax, start, end, color=color, dashed=dashed, head=False)
    arrow(ax, points[-2], points[-1], color=color, dashed=dashed, head=True)
    if text and text_xy:
        ax.text(
            text_xy[0],
            text_xy[1],
            text,
            fontsize=11.5,
            weight="bold",
            color=color,
            ha="center",
            va="center",
            bbox={"boxstyle": "round,pad=0.18", "facecolor": BG, "edgecolor": "none"},
        )


def main():
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Noto Sans CJK SC", "DejaVu Sans"],
            "axes.unicode_minus": False,
        }
    )
    fig, ax = plt.subplots(figsize=(21, 11), dpi=180)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.5, 0.975, "AR5阶段感知六维导纳控制流程", ha="center", va="top", fontsize=25, weight="bold", color="#153247")
    ax.text(0.5, 0.936, "示教轨迹为移动中心 · 异常扳手驱动位姿修正 · 严重接触时暂停轨迹但保持导纳", ha="center", va="top", fontsize=13, color=MUTED)

    ax.text(0.045, 0.885, "A  上线准备", fontsize=15, weight="bold", color=BLUE)
    box(ax, 0.050, 0.785, 0.250, 0.075, "1  启动与参数校验", "加载 M/D/K、限幅、包络、阶段掩码和示教点")
    box(ax, 0.375, 0.785, 0.250, 0.075, "2  力传感器清零", "等待新鲜数据；静止 2 s tare；检查清零稳定性")
    box(ax, 0.700, 0.785, 0.250, 0.075, "3  上线前安全检查", "P_SAFE、软限位、checkPath、控制权与人工确认")
    arrow(ax, (0.300, 0.823), (0.375, 0.823))
    arrow(ax, (0.625, 0.823), (0.700, 0.823))

    ax.text(0.045, 0.710, "B  1 kHz 实时感知与异常力提取", fontsize=15, weight="bold", color=BLUE)
    box(ax, 0.740, 0.600, 0.220, 0.080, "4  采集六维力与状态", "W_raw、TCP位姿、关节与肘部状态")
    box(ax, 0.505, 0.600, 0.210, 0.080, "5  扳手坐标变换", "清零 → Sensor/Tool → 当前Base参考方向")
    box(ax, 0.270, 0.600, 0.210, 0.080, "6  硬限与看门狗", "数据≤50 ms；合力<35 N；力矩<1.50 N·m")
    box(ax, 0.035, 0.600, 0.210, 0.080, "7  阶段正常力包络", "插值 c(s)、h(s)，提取 W_excess")
    poly_arrow(ax, [(0.825, 0.785), (0.825, 0.715), (0.850, 0.715), (0.850, 0.680)], color=BLUE)
    arrow(ax, (0.740, 0.640), (0.715, 0.640))
    arrow(ax, (0.505, 0.640), (0.480, 0.640))
    arrow(ax, (0.270, 0.640), (0.245, 0.640))

    ax.text(0.045, 0.535, "C  导纳求解与轨迹调节", fontsize=15, weight="bold", color=BLUE)
    decision(ax, 0.120, 0.440, 0.190, 0.105, "8  扰动预置 /\n尚未启动回中？")
    poly_arrow(ax, [(0.140, 0.600), (0.140, 0.515), (0.120, 0.515), (0.120, 0.493)], color=BLUE)

    box(ax, 0.245, 0.458, 0.195, 0.065, "平滑建立测试偏差", "五次曲线；接触立即停止", edge=ORANGE, fill="#FFF4E8")
    box(ax, 0.245, 0.350, 0.195, 0.075, "六维导纳离散求解", "滤波/死区 → M/D/K → 三层限幅", edge=BLUE, fill="#EDF5FB")
    arrow(ax, (0.215, 0.463), (0.245, 0.490), color=ORANGE, text="是", text_offset=(-0.002, 0.021))
    arrow(ax, (0.215, 0.417), (0.245, 0.388), color=BLUE, text="否", text_offset=(-0.002, -0.020))

    decision(ax, 0.555, 0.440, 0.185, 0.105, "9  严重异常并\n持续 0.10 s？")
    arrow(ax, (0.440, 0.490), (0.462, 0.463), color=ORANGE)
    arrow(ax, (0.440, 0.388), (0.462, 0.417), color=BLUE)

    box(ax, 0.670, 0.458, 0.195, 0.065, "轨迹调节器进入恢复", "rate降至0；导纳继续卸力", edge=ORANGE, fill="#FFF4E8")
    box(ax, 0.670, 0.350, 0.195, 0.075, "继续名义轨迹", "小偏差在线修正；rate保持1", edge=GREEN, fill="#EDF8F0")
    arrow(ax, (0.648, 0.463), (0.670, 0.490), color=ORANGE, text="是", text_offset=(0.002, 0.021))
    arrow(ax, (0.648, 0.417), (0.670, 0.388), color=GREEN, text="否", text_offset=(0.002, -0.020))

    ax.text(0.045, 0.285, "D  位姿输出、诊断与任务判定", fontsize=15, weight="bold", color=BLUE)
    box(ax, 0.730, 0.165, 0.230, 0.080, "10  位姿合成并输出", "p_cmd=p_nom+Δp；R_cmd=Exp([Δr]×)R_nom")
    box(ax, 0.475, 0.165, 0.220, 0.080, "11  执行链与跟踪检查", "desired ↔ tcpPose_c ↔ tcpPose_m")
    decision(ax, 0.345, 0.205, 0.185, 0.105, "12  就位、继续\n或故障？")
    poly_arrow(ax, [(0.865, 0.490), (0.910, 0.490), (0.910, 0.305), (0.890, 0.245)], color=ORANGE)
    poly_arrow(ax, [(0.767, 0.350), (0.767, 0.300), (0.800, 0.245)], color=GREEN)
    arrow(ax, (0.730, 0.205), (0.695, 0.205))
    arrow(ax, (0.475, 0.205), (0.438, 0.205))

    box(ax, 0.035, 0.215, 0.185, 0.060, "成功就位", "seat=REACHED", edge=GREEN, fill="#EDF8F0")
    box(ax, 0.035, 0.105, 0.185, 0.065, "安全退出", "stop→断网→下电→manual", edge=RED, fill="#FDEEEE")
    arrow(ax, (0.252, 0.228), (0.220, 0.245), color=GREEN, text="成功", text_offset=(-0.002, 0.021))
    arrow(ax, (0.252, 0.182), (0.220, 0.138), color=RED, text="故障", text_offset=(-0.004, -0.021))

    poly_arrow(
        ax,
        [(0.345, 0.153), (0.345, 0.055), (0.980, 0.055), (0.980, 0.720), (0.850, 0.720), (0.850, 0.680)],
        color=BLUE,
        dashed=True,
        text="未结束：返回实时循环",
        text_xy=(0.665, 0.055),
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight", pad_inches=0.20, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(OUT.resolve())


if __name__ == "__main__":
    main()
