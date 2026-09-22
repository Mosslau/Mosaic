# project/vehdash/clean.py —— 车队遥测清洗流水线
# 验证环境：Python 3.13 + pandas；本机实测 Python 3.13.12 + pandas 3.0.5
"""清洗流水线：排序 → 去重 → 物理量程 → 孤立尖峰。

语义与 examples/ex02 同源：量程取 data.RANGES，尖峰按「秒级物理跳变量级」判定
（1s 内车速变 20km/h+ 等不可能是真信号）。逐步骤计数并返回 CleanStats ——
清洗可审计是 ph18 的硬要求（roadmap 必会概念）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from vehdash.data import RANGES

# 秒级物理跳变量级（剔除单点毛刺用，量纲是「每秒能变多少」）
SPIKE_JUMPS: dict[str, float] = {
    "speed_kmh": 20.0,
    "pack_temp_c": 10.0,
    "pack_current_a": 80.0,
    "power_kw": 30.0,
}


@dataclass
class CleanStats:
    raw_rows: int
    dup_removed: int = 0
    phys_removed: dict[str, int] = field(default_factory=dict)
    spike_removed: dict[str, int] = field(default_factory=dict)
    final_rows: int = 0

    def summary_lines(self) -> list[str]:
        lines = [
            f"  原始行数：{self.raw_rows}",
            f"  去除重复：{self.dup_removed}",
            "  物理范围剔除：" + ", ".join(f"{c}={n}" for c, n in self.phys_removed.items()),
            "  孤立尖峰剔除：" + ", ".join(f"{c}={n}" for c, n in self.spike_removed.items()),
            f"  清洗后行数：{self.final_rows}",
        ]
        return lines


def clean_fleet(df: pd.DataFrame) -> tuple[pd.DataFrame, CleanStats]:
    """清洗入口：排序（滚动窗口前提）→ 去重 → 物理量程 → 孤立尖峰。"""
    stats = CleanStats(raw_rows=len(df))
    df = df.sort_values(["vehicle_id", "ts"]).reset_index(drop=True)
    df = df.drop_duplicates().reset_index(drop=True)
    stats.dup_removed = stats.raw_rows - len(df)

    df, stats.phys_removed = _drop_physical(df)
    df, stats.spike_removed = _drop_isolated_spikes(df)
    stats.final_rows = len(df)
    return df, stats


def _drop_physical(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    removed: dict[str, int] = {}
    keep = pd.Series(True, index=df.index)
    for col, (lo, hi) in RANGES.items():
        ok = df[col].between(lo, hi)
        removed[col] = int((~ok).sum())
        keep &= ok
    return df[keep].copy(), removed


def _drop_isolated_spikes(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    removed: dict[str, int] = {}
    keep = pd.Series(True, index=df.index)
    for col, jump in SPIKE_JUMPS.items():
        if col not in df.columns:
            continue
        # 先按车滚动：时间已全局排序，按车辆分组重置索引再滚动（避免跨车窗口）
        medians = []
        for _vid, grp in df.groupby("vehicle_id", sort=False):
            med = grp[col].rolling(7, center=True, min_periods=3).median()
            med.index = grp.index
            medians.append(med)
        window_median = pd.concat(medians).sort_index()
        is_spike = (df[col] - window_median).abs() > jump
        removed[col] = int(is_spike.sum())
        keep &= ~is_spike
    return df[keep].copy(), removed
