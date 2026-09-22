#!/usr/bin/env python3
# examples/ex02-telemetry-clean.py —— 车辆遥测数据清洗（主文档 3.2）
# 验证环境（目标）：Python 3.13 + pandas 2.x/3.x；本机实测 Python 3.13.12 + pandas 3.0.5
# 运行：python3 ex02-telemetry-clean.py（打印教学输出 + 断言自检，失败退出码非 0）
# 测试：python3 -m pytest ex02-telemetry-clean.py -q（收集 test_* 跑断言）
# lint：ruff check ex02-telemetry-clean.py
# 验证状态：已验证（Python 3.13.12 + pandas 3.0.5 本机实测：自检与 pytest 全绿）
"""车辆遥测数据清洗流水线：去重 → 物理范围 → 孤立尖峰 → 时间对齐/补洞。

衔接 ph09 的 pandas 基础：本示例把 ph09 讲过的 resample/rolling/fillna 组合成一条
**可复用的清洗管线**，并给每步计数 —— 清洗必须可审计，是 roadmap 必会概念「自动化
测试要可重复和可审计」在数据侧的体现。数据在脚本内自造并写 /tmp，不依赖网络。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

# 车辆遥测列物理范围（超出即判定为传感器/记录异常，直接剔除）
# 列车队级 schema 在本阶段各示例间保持一致（ex02~ex04/ex07/project 共用）
PHYSICAL_RANGES: dict[str, tuple[float, float]] = {
    "speed_kmh": (0.0, 220.0),
    "soc_pct": (0.0, 100.0),
    "pack_voltage_v": (250.0, 420.0),
    "pack_temp_c": (-40.0, 65.0),
    "pack_current_a": (-300.0, 400.0),  # 约定：放电为负、回充为正（本阶段样例数据用）
    "power_kw": (-300.0, 300.0),
}

# 孤立尖峰判据：与「局部中位数 ±2s」的偏差超过该列的**秒级物理跳变量级**
# 就判定为毛刺（如 1s 内车速变 20km/h+、温度变 10℃+ 不可能是真信号）。
SPIKE_JUMPS: dict[str, float] = {
    "speed_kmh": 20.0,
    "pack_temp_c": 10.0,
    "pack_current_a": 80.0,
    "power_kw": 30.0,
}


@dataclass
class CleanReport:
    """清洗各步骤的计数 —— 让「清洗改了什么」可复现、可写进测试与报告。"""

    raw_rows: int
    dup_removed: int = 0
    phys_removed: dict[str, int] = field(default_factory=dict)
    spike_removed: dict[str, int] = field(default_factory=dict)
    filled_rows: int = 0  # 时间对齐后，实际被前向填充补上的网格行数
    dropped_gap_rows: int = 0  # 超过 ffill 上限、保持 NaN 并最终丢弃的缺口行数
    final_rows: int = 0

    def summary(self) -> str:
        lines = [
            f"  原始行数：{self.raw_rows}",
            f"  去除重复：{self.dup_removed}",
            "  物理范围剔除：" + ", ".join(f"{c}={n}" for c, n in self.phys_removed.items()),
            "  孤立尖峰剔除：" + ", ".join(f"{c}={n}" for c, n in self.spike_removed.items()),
            f"  时间对齐补洞（≤{FFILL_LIMIT}s）：{self.filled_rows}",
            f"  超长缺口丢弃：{self.dropped_gap_rows}",
            f"  清洗后行数：{self.final_rows}",
        ]
        return "\n".join(lines)


FFILL_LIMIT = 3  # 小缺口（≤3s）前向填充；更长缺口视为数据缺口不伪造


def generate_telemetry(
    vehicles: tuple[str, ...] = ("V001", "V002", "V003"),
    seconds: int = 120,
    seed: int = 7,
) -> pd.DataFrame:
    """自造遥测样本：1Hz、基础量 + 噪声，再**有意注入**脏数据供清洗演示。

    注入的脏数据（全部确定性，靠 seed）：
    - 1 组完全重复的行（去重步骤处理）
    - 物理越界：speed=300 km/h、soc=-5%、voltage=500 V（物理范围步骤处理）
    - 孤立尖峰：pack_temp_c 单点 +25℃、speed 单点归零、current 单点突变到 +250 A
      （孤立尖峰步骤处理；250A 在物理范围内，只能靠尖峰检测抓住）
    - 连续 5s 整段缺失（超过 3s 填充上限 → 缺口保留为 NaN 并丢弃）
    """
    rng = np.random.default_rng(seed)
    t = np.arange(seconds, dtype=float)
    frames: list[pd.DataFrame] = []
    for vehicle_id in vehicles:
        speed = 45 + 35 * np.sin(t / 25.0) + rng.normal(0, 0.4, seconds)
        soc = np.clip(80 - t * 0.05 + rng.normal(0, 0.05, seconds), 0, 100)
        pack_temp = 28 + 0.05 * t + rng.normal(0, 0.3, seconds)
        pack_current = -20 - (speed / 10.0) + rng.normal(0, 1.0, seconds)  # 放电为负
        pack_voltage = 380 + 0.02 * t + rng.normal(0, 0.5, seconds)
        df = pd.DataFrame(
            {
                "ts": t + 1_700_000_000,
                "vehicle_id": vehicle_id,
                "speed_kmh": speed,
                "soc_pct": soc,
                "pack_voltage_v": pack_voltage,
                "pack_temp_c": pack_temp,
                "pack_current_a": pack_current,
                "power_kw": pack_voltage * pack_current / 1000.0,  # 一致性：V*I/1000
            }
        )
        # --- 按车注入脏数据 ---
        df.loc[10, "speed_kmh"] = 300.0  # 物理越界
        df.loc[11, "soc_pct"] = -5.0  # 物理越界
        df.loc[12, "pack_voltage_v"] = 500.0  # 物理越界
        df.loc[40, "pack_temp_c"] += 25.0  # 孤立尖峰（单点）
        df.loc[60, "speed_kmh"] = 0.0  # 与前后严重跳变的孤立尖峰
        df.loc[61, "pack_current_a"] = 250.0  # 幅值在物理范围内、但方向突变
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    # 全局注入：连续 5s 整段缺失（ts 80~84 全删）
    df = df[~df["ts"].between(1_700_000_080, 1_700_000_084)].copy()
    # 注入 1 组完全重复行
    df = pd.concat([df, df.iloc[5:6]], ignore_index=True)
    # 打乱行序（模拟真实采集乱序到达）
    df = df.sample(frac=1, random_state=rng).reset_index(drop=True)
    return df


def _drop_physical(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """逐列按物理范围剔除，返回剩余数据与每列剔除数。"""
    removed: dict[str, int] = {}
    keep = pd.Series(True, index=df.index)
    for col, (low, high) in PHYSICAL_RANGES.items():
        in_range = df[col].between(low, high)
        removed[col] = int((~in_range).sum())
        keep &= in_range
    return df[keep].copy(), removed


def _drop_isolated_spikes(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """孤立尖峰剔除：与局部中位数（±2s）偏差超过秒级物理跳变阈值即剔除。

    阈值是**物理量纲的常量**而非统计量（SPIKE_JUMPS）：对趋势/噪声不敏感，
    只抓「一秒内不可能出现的跳变」，行为可预测、可解释。
    """
    removed: dict[str, int] = {}
    keep = pd.Series(True, index=df.index)
    for col, jump in SPIKE_JUMPS.items():
        window_median = df[col].rolling(5, center=True, min_periods=3).median()
        is_spike = (df[col] - window_median).abs() > jump
        removed[col] = int(is_spike.sum())
        keep &= ~is_spike
    return df[keep].copy(), removed


def _align_time(
    df: pd.DataFrame, freq: str = "1s", fill_limit: int = FFILL_LIMIT
) -> tuple[pd.DataFrame, int, int]:
    """按车对齐到 1Hz 时间网格：≤fill_limit 秒的缺口前向填充，超长缺口丢弃。

    返回（对齐后的数据、实际填充行数、因超长缺口丢弃的行数）。
    """
    parts: list[pd.DataFrame] = []
    filled_total = 0
    dropped_total = 0
    for _vid, grp in df.groupby("vehicle_id", sort=False):
        grp = grp.sort_values("ts")
        grp = grp.set_index(pd.to_datetime(grp["ts"], unit="s"))
        grid = grp.resample(freq).asfreq()  # 全网格：缺失处成 NaN 行
        cols = list(PHYSICAL_RANGES)  # 参与前向填充的量列
        was_nan = grid[cols].isna().any(axis=1)
        grid[cols] = grid[cols].ffill(limit=fill_limit)
        still_nan = grid[cols].isna().any(axis=1)
        # 从 DatetimeIndex 重建数值时间戳（网格行的 ts 统一为整秒）
        grid["ts"] = grid.index.astype("int64") / 1_000_000_000
        filled_total += int((was_nan & ~still_nan).sum())
        dropped_total += int(still_nan.sum())
        parts.append(grid[~still_nan].copy())
    aligned = pd.concat(parts).reset_index(drop=True)  # 先丢 DatetimeIndex，避免列/索引歧义
    aligned = aligned.sort_values(["vehicle_id", "ts"]).reset_index(drop=True)
    return aligned, filled_total, dropped_total


def clean_telemetry(df: pd.DataFrame) -> tuple[pd.DataFrame, CleanReport]:
    """清洗流水线入口：去重 → 物理范围 → 孤立尖峰 → 时间对齐补洞。"""
    report = CleanReport(raw_rows=len(df))
    # 0. 时间排序：滚动窗口（去重/尖峰）依赖时间有序——真实采集乱序到达，先排好
    df = df.sort_values(["vehicle_id", "ts"]).reset_index(drop=True)
    # 1. 去重（按全列；真实场景通常按 (ts, vehicle_id) 指纹）
    df = df.drop_duplicates().reset_index(drop=True)
    report.dup_removed = report.raw_rows - len(df)
    # 2. 物理范围
    df, report.phys_removed = _drop_physical(df)
    # 3. 孤立尖峰
    df, report.spike_removed = _drop_isolated_spikes(df)
    # 4. 时间对齐 + 补洞
    df, report.filled_rows, report.dropped_gap_rows = _align_time(df)
    report.final_rows = len(df)
    return df, report


def main() -> None:
    vehicles, seconds = ("V001", "V002", "V003"), 120
    df_raw = generate_telemetry(vehicles, seconds)
    print(f"自造原始数据：{len(df_raw)} 行（含重复/越界/尖峰/缺段脏数据）")
    cleaned, report = clean_telemetry(df_raw)
    print("== 清洗报告 ==")
    print(report.summary())

    # 干净数据上的不变量断言
    assert cleaned["soc_pct"].between(0, 100).all()
    assert cleaned["speed_kmh"].between(0, 220).all()
    assert cleaned["pack_voltage_v"].between(250, 420).all()
    assert report.dup_removed == 1
    assert report.phys_removed["speed_kmh"] == len(vehicles)  # 每车一个 300 km/h
    assert report.spike_removed["speed_kmh"] == len(vehicles)  # 每车一个瞬间归零
    assert report.spike_removed["pack_temp_c"] == len(vehicles)  # 每车一个 +25℃ 尖峰
    # 超长缺口：5s 中 ≤3s 被 ffill 补上、>3s 的部分丢弃 → 清洗后比理想满网格少 2 行/车
    perfect_grid = len(vehicles) * seconds
    assert report.final_rows == perfect_grid - report.dropped_gap_rows
    assert report.dropped_gap_rows == len(vehicles) * 2
    # 清洗后不存在秒级温度跳变 >10℃（尖峰已被替换为邻居值）
    assert cleaned["pack_temp_c"].diff().abs().max() < 10.0

    # 产物纪律：CSV 写 /tmp，仓库不残留
    out_dir = Path("/tmp/ph18-ex02")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "cleaned_telemetry.csv"
    cleaned.to_csv(out_csv, index=False)
    print(f"\n清洗结果已写：{out_csv}（{report.final_rows} 行）")
    print("\n自检通过：清洗报告、物理/尖峰剔除、时间对齐断言全绿")


def _mini_frame() -> pd.DataFrame:
    """最小构造帧（测试用）：覆盖全部必需列。"""
    return pd.DataFrame(
        {
            "ts": [1.0, 2.0, 3.0],
            "vehicle_id": ["V001"] * 3,
            "speed_kmh": [10.0, 11.0, 12.0],
            "soc_pct": [80.0, 79.0, 78.0],
            "pack_voltage_v": [380.0, 381.0, 382.0],
            "pack_temp_c": [28.0, 28.1, 28.2],
            "pack_current_a": [-20.0, -21.0, -22.0],
            "power_kw": [-7.6, -8.0, -8.4],
        }
    )


def test_duplicate_rows_removed() -> None:
    df = pd.concat([_mini_frame(), _mini_frame().iloc[1:2]])
    cleaned, report = clean_telemetry(df)
    assert report.dup_removed == 1
    assert len(cleaned) == 3


def test_physical_out_of_range_dropped() -> None:
    df = _mini_frame()
    df.loc[1, ["speed_kmh", "soc_pct"]] = [300.0, -5.0]  # 同一行越两个量
    cleaned, report = clean_telemetry(df)
    assert report.phys_removed["speed_kmh"] == 1
    assert report.phys_removed["soc_pct"] == 1
    assert 300.0 not in set(cleaned["speed_kmh"])


def test_isolated_spike_removed() -> None:
    df = _mini_frame()
    df.loc[1, "pack_temp_c"] += 25.0  # 单点 +25℃
    cleaned, report = clean_telemetry(df)
    assert report.spike_removed["pack_temp_c"] == 1
    # 尖峰被剔除后由邻居 ffill 替代，最终数据里不保留 53℃ 那行
    assert (cleaned["pack_temp_c"] < 40).all()


def test_small_gap_filled_long_gap_dropped() -> None:
    df = pd.concat([_mini_frame(), _mini_frame().assign(ts=_mini_frame()["ts"] + 3.0)])
    df = df[~df["ts"].isin([3.0, 4.0, 5.0])].copy()  # 挖出 3s 连续缺口
    aligned, filled, dropped = _align_time(df)
    assert filled == 3  # 3s 缺口被前向填充
    assert dropped == 0
    assert aligned["ts"].nunique() == 6


if __name__ == "__main__":
    main()
