#!/usr/bin/env python3
"""Generate a compact, event-aligned comparison figure from wrench CSV logs.

Each run is passed as LABEL=CSV_PATH. The CSV must contain:
elapsed_s, fx_n, fy_n, fz_n, mx_nm, my_nm, mz_nm.

Example:
    python tools/plot_key_windows.py \
      --run "基线=baseline.csv" \
      --run "导纳=admittance.csv" \
      --output analysis_output/comparison.png
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


@dataclass
class RunData:
    label: str
    path: Path
    time_s: np.ndarray
    force_n: np.ndarray
    torque_nm: np.ndarray
    contact_index: int
    peak_index: int
    sample_rate_hz: float

    @property
    def aligned_time_s(self) -> np.ndarray:
        return self.time_s - self.time_s[self.contact_index]

    @property
    def active_time_s(self) -> np.ndarray:
        return self.time_s[self.contact_index :] - self.time_s[self.contact_index]

    @property
    def active_progress(self) -> np.ndarray:
        active = self.active_time_s
        if len(active) < 2 or active[-1] <= 0:
            return np.zeros_like(active)
        return active / active[-1] * 100.0


def parse_run(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--run 必须使用 LABEL=CSV_PATH 格式")
    label, raw_path = value.split("=", 1)
    label = label.strip()
    path = Path(raw_path).expanduser().resolve()
    if not label:
        raise argparse.ArgumentTypeError("--run 的 LABEL 不能为空")
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"CSV 不存在：{path}")
    return label, path


def centered_mean(values: np.ndarray, window_samples: int) -> np.ndarray:
    window_samples = max(1, int(window_samples))
    if window_samples == 1:
        return values.copy()
    left = window_samples // 2
    right = window_samples - left
    indices = np.arange(len(values))
    starts = np.maximum(0, indices - left)
    ends = np.minimum(len(values), indices + right)
    cumulative = np.concatenate(([0.0], np.cumsum(values, dtype=float)))
    return (cumulative[ends] - cumulative[starts]) / (ends - starts)


def sustained_first(values: np.ndarray, threshold: float, samples: int) -> int:
    samples = max(1, int(samples))
    above = values >= threshold
    counts = np.convolve(above.astype(np.int32), np.ones(samples, dtype=np.int32), mode="valid")
    hits = np.flatnonzero(counts >= samples)
    return int(hits[0]) if len(hits) else 0


def load_run(
    label: str,
    path: Path,
    smoothing_ms: float,
    contact_threshold_n: float,
    contact_hold_ms: float,
) -> RunData:
    times: list[float] = []
    forces: list[float] = []
    torques: list[float] = []
    required = ("elapsed_s", "fx_n", "fy_n", "fz_n", "mx_nm", "my_nm", "mz_nm")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or any(name not in reader.fieldnames for name in required):
            raise ValueError(f"{path} 缺少必要列：{', '.join(required)}")
        for row in reader:
            t = float(row["elapsed_s"])
            f = [float(row[name]) for name in ("fx_n", "fy_n", "fz_n")]
            m = [float(row[name]) for name in ("mx_nm", "my_nm", "mz_nm")]
            if not all(math.isfinite(v) for v in (t, *f, *m)):
                continue
            times.append(t)
            forces.append(math.sqrt(sum(v * v for v in f)))
            torques.append(math.sqrt(sum(v * v for v in m)))
    if len(times) < 10:
        raise ValueError(f"{path} 有效数据不足")

    time_s = np.asarray(times, dtype=float)
    force_raw = np.asarray(forces, dtype=float)
    torque_raw = np.asarray(torques, dtype=float)
    duration_s = float(time_s[-1] - time_s[0])
    if duration_s <= 0:
        raise ValueError(f"{path} 时间戳没有递增")
    # CSV writes may arrive in short bursts, making median(dt) look several
    # times faster than the true acquisition rate. The full-span effective
    # rate preserves the intended smoothing and contact-hold duration.
    sample_rate_hz = (len(time_s) - 1) / duration_s
    smooth_samples = max(1, round(smoothing_ms * 1e-3 * sample_rate_hz))
    hold_samples = max(1, round(contact_hold_ms * 1e-3 * sample_rate_hz))
    force_n = centered_mean(force_raw, smooth_samples)
    torque_nm = centered_mean(torque_raw, smooth_samples)
    contact_index = sustained_first(force_n, contact_threshold_n, hold_samples)
    peak_index = int(np.argmax(force_n))
    return RunData(
        label=label,
        path=path,
        time_s=time_s,
        force_n=force_n,
        torque_nm=torque_nm,
        contact_index=contact_index,
        peak_index=peak_index,
        sample_rate_hz=sample_rate_hz,
    )


def plot_window(ax: plt.Axes, run: RunData, start_s: float, end_s: float, color: str) -> None:
    aligned = run.aligned_time_s
    mask = (aligned >= start_s) & (aligned <= end_s)
    if np.any(mask):
        ax.plot(aligned[mask], run.force_n[mask], color=color, linewidth=2.0, label=run.label)


def plot_peak_window(ax: plt.Axes, run: RunData, before_s: float, after_s: float, color: str) -> None:
    relative = run.time_s - run.time_s[run.peak_index]
    mask = (relative >= -before_s) & (relative <= after_s)
    if np.any(mask):
        ax.plot(relative[mask], run.force_n[mask], color=color, linewidth=2.0, label=run.label)
        ax.scatter([0], [run.force_n[run.peak_index]], color=color, s=35, zorder=3)


def metrics(run: RunData) -> dict[str, float]:
    active_force = run.force_n[run.contact_index :]
    active_torque = run.torque_nm[run.contact_index :]
    return {
        "peak_force_n": float(np.max(active_force)),
        "p95_force_n": float(np.percentile(active_force, 95)),
        "peak_torque_nm": float(np.max(active_torque)),
        "active_duration_s": float(run.active_time_s[-1]),
    }


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Noto Sans CJK SC", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "figure.facecolor": "#F4F7FA",
            "axes.facecolor": "#FFFFFF",
            "axes.edgecolor": "#AAB8C2",
            "axes.labelcolor": "#263746",
            "xtick.color": "#526675",
            "ytick.color": "#526675",
            "grid.color": "#DCE5EB",
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="绘制六维力CSV关键窗口对比图")
    parser.add_argument("--run", action="append", type=parse_run, required=True, help="LABEL=CSV_PATH，可重复")
    parser.add_argument("--output", type=Path, required=True, help="输出PNG路径")
    parser.add_argument("--metrics-output", type=Path, help="可选：输出指标CSV")
    parser.add_argument("--title", default="主板装配六维力关键窗口对比", help="图表总标题")
    parser.add_argument(
        "--note",
        default="数据源为传感器坐标原始六维记录；装配结果需结合控制器日志或现场记录判断。",
        help="指标区域底部说明",
    )
    parser.add_argument("--smoothing-ms", type=float, default=100.0, help="平滑窗口，默认100 ms")
    parser.add_argument("--contact-threshold-n", type=float, default=1.0, help="首次接触阈值，默认1 N")
    parser.add_argument("--contact-hold-ms", type=float, default=50.0, help="接触持续时间，默认50 ms")
    parser.add_argument("--contact-window-s", type=float, default=12.0, help="首次接触后显示时长")
    parser.add_argument("--peak-before-s", type=float, default=10.0, help="峰值前显示时长")
    parser.add_argument("--peak-after-s", type=float, default=2.0, help="峰值后显示时长")
    args = parser.parse_args()
    if len(args.run) < 2:
        parser.error("对比图至少需要两个 --run")
    if args.smoothing_ms <= 0 or args.contact_hold_ms <= 0:
        parser.error("平滑和持续时间必须为正数")

    runs = [
        load_run(label, path, args.smoothing_ms, args.contact_threshold_n, args.contact_hold_ms)
        for label, path in args.run
    ]
    configure_style()
    colors = ["#1976D2", "#E65100", "#2E7D32", "#7B1FA2", "#00838F", "#C62828", "#455A64"]

    fig = plt.figure(figsize=(16, 9), constrained_layout=True)
    grid = fig.add_gridspec(2, 3, height_ratios=[1.05, 1.0])
    ax_overall = fig.add_subplot(grid[0, :])
    ax_contact = fig.add_subplot(grid[1, 0])
    ax_peak = fig.add_subplot(grid[1, 1])
    ax_metrics = fig.add_subplot(grid[1, 2])

    for index, run in enumerate(runs):
        color = colors[index % len(colors)]
        ax_overall.plot(
            run.active_progress,
            run.force_n[run.contact_index :],
            color=color,
            linewidth=1.8,
            label=f"{run.label}（{run.sample_rate_hz:.0f} Hz）",
        )
        plot_window(ax_contact, run, -2.0, args.contact_window_s, color)
        plot_peak_window(ax_peak, run, args.peak_before_s, args.peak_after_s, color)

    ax_overall.set_title("全过程对比：首次持续接触后的记录区间归一化", loc="left", fontsize=16, weight="bold")
    ax_overall.set_xlabel("接触后记录区间归一化进度 / %")
    ax_overall.set_ylabel("合力 / N")
    ax_overall.set_xlim(0, 100)
    ax_overall.grid(True, alpha=0.75)
    ax_overall.legend(ncol=min(4, len(runs)), frameon=False, loc="upper left")
    ax_overall.text(
        1.0,
        1.02,
        f"{args.smoothing_ms:.0f} ms 平滑｜接触判定：≥{args.contact_threshold_n:g} N 持续 {args.contact_hold_ms:.0f} ms",
        transform=ax_overall.transAxes,
        ha="right",
        va="bottom",
        fontsize=10,
        color="#526675",
    )

    ax_contact.axvline(0, color="#9AAAB5", linestyle="--", linewidth=1)
    ax_contact.set_title("关键窗口 1：首次接触", loc="left", fontsize=14, weight="bold")
    ax_contact.set_xlabel("相对首次接触时间 / s")
    ax_contact.set_ylabel("合力 / N")
    ax_contact.grid(True, alpha=0.75)

    ax_peak.axvline(0, color="#9AAAB5", linestyle="--", linewidth=1)
    ax_peak.set_title("关键窗口 2：最大载荷", loc="left", fontsize=14, weight="bold")
    ax_peak.set_xlabel("相对峰值时间 / s")
    ax_peak.set_ylabel("合力 / N")
    ax_peak.grid(True, alpha=0.75)

    table_rows = []
    calculated = []
    for run in runs:
        result = metrics(run)
        calculated.append(result)
        table_rows.append(
            [
                run.label,
                f"{result['peak_force_n']:.2f}",
                f"{result['p95_force_n']:.2f}",
                f"{result['peak_torque_nm']:.3f}",
                f"{result['active_duration_s']:.1f}",
            ]
        )
    ax_metrics.axis("off")
    ax_metrics.set_title("关键指标", loc="left", fontsize=14, weight="bold", pad=14)
    table = ax_metrics.table(
        cellText=table_rows,
        colLabels=["运行", "峰值力/N", "P95力/N", "峰值矩/Nm", "接触后记录/s"],
        cellLoc="center",
        colLoc="center",
        loc="upper center",
        bbox=[0.0, 0.42, 1.0, 0.48],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9.5)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#D6E0E6")
        cell.set_linewidth(0.8)
        if row == 0:
            cell.set_facecolor("#DCEAF5")
            cell.set_text_props(weight="bold", color="#263746")
        else:
            cell.set_facecolor("#FFFFFF")
    if len(runs) == 2:
        first, second = calculated
        delta_force = (second["peak_force_n"] / first["peak_force_n"] - 1.0) * 100.0
        delta_torque = (second["peak_torque_nm"] / first["peak_torque_nm"] - 1.0) * 100.0
        ax_metrics.text(
            0.0,
            0.29,
            f"{runs[1].label} 相对 {runs[0].label}",
            transform=ax_metrics.transAxes,
            fontsize=12,
            weight="bold",
            color="#263746",
        )
        ax_metrics.text(
            0.0,
            0.20,
            f"峰值合力 {delta_force:+.1f}%   峰值合力矩 {delta_torque:+.1f}%",
            transform=ax_metrics.transAxes,
            fontsize=15,
            weight="bold",
            color="#1976D2" if delta_force <= 0 else "#C62828",
        )
    ax_metrics.text(
        0.0,
        0.06,
        args.note,
        transform=ax_metrics.transAxes,
        fontsize=9.5,
        color="#526675",
        wrap=True,
    )

    fig.suptitle(args.title, fontsize=22, weight="bold", x=0.02, ha="left")
    args.output = args.output.expanduser().resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)

    if args.metrics_output:
        metrics_path = args.metrics_output.expanduser().resolve()
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with metrics_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(["label", "source_csv", "sample_rate_hz", "contact_time_s", "peak_force_n", "p95_force_n", "peak_torque_nm", "active_duration_s"])
            for run, result in zip(runs, calculated):
                writer.writerow(
                    [
                        run.label,
                        str(run.path),
                        f"{run.sample_rate_hz:.3f}",
                        f"{run.time_s[run.contact_index]:.6f}",
                        f"{result['peak_force_n']:.6f}",
                        f"{result['p95_force_n']:.6f}",
                        f"{result['peak_torque_nm']:.6f}",
                        f"{result['active_duration_s']:.6f}",
                    ]
                )

    print(f"图表已生成：{args.output}")
    for run, result in zip(runs, calculated):
        print(
            f"{run.label}: peak_force={result['peak_force_n']:.2f} N, "
            f"p95_force={result['p95_force_n']:.2f} N, "
            f"peak_torque={result['peak_torque_nm']:.3f} Nm, "
            f"active_duration={result['active_duration_s']:.1f} s"
        )


if __name__ == "__main__":
    main()
