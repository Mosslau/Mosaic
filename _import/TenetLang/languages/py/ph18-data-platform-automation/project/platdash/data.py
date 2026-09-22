# project/platdash/data.py —— 平台指标样例生成与读取
# 验证环境：Python 3.13 + numpy/pandas；本机实测 Python 3.13.9 + pandas（见 README 验收标准）
"""确定性平台样例数据（教学用）：3 个服务实例 × 20 分钟 1Hz 指标 + 刻意埋的脏点。

脏点设计（保证清洗/分析有活干、断言可写）：
- 每个服务实例在固定时刻有 1 个延迟越界点（5000 ms）与 1 个孤立磁盘温度尖峰
- V002 有一段持续高温（82℃，>75℃ 的"严重过热"刻意安排 9s）
- V003 有一段小缺口（5s 掉点）
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# 列 schema（与 examples/ex02、主文档 3.2 一致；全阶段共用一份）
PLATFORM_COLUMNS = (
    "ts",
    "service_id",
    "latency_ms",
    "cpu_pct",
    "mem_used_gb",
    "disk_temp_c",
    "net_io_mb_s",
    "power_w",
)

# 量程规格（与清洗共用，纯函数模块间以常量形式共享）
RANGES: dict[str, tuple[float, float]] = {
    "latency_ms": (0.0, 2000.0),
    "cpu_pct": (0.0, 100.0),
    "mem_used_gb": (0.0, 256.0),
    "disk_temp_c": (10.0, 90.0),
    "net_io_mb_s": (0.0, 2000.0),
    "power_w": (20.0, 600.0),
}

# 严重过热阈值（>75℃ 计为过热秒；真实平台按机型标定，教学取整数）
HOT_TEMP_C = 75.0


def generate_platform(
    services: tuple[str, ...] = ("V001", "V002", "V003"),
    minutes: int = 20,
    seed: int = 17,
) -> pd.DataFrame:
    """生成平台指标（未清洗：乱序 + 埋点），与文件解耦，便于测试直接用 DataFrame。"""
    rng = np.random.default_rng(seed)
    seconds = minutes * 60
    t = np.arange(seconds, dtype=float)
    frames: list[pd.DataFrame] = []
    for service_id in services:
        base_latency = {"V001": 50, "V002": 45, "V003": 60}[service_id]
        latency = base_latency + 15 * np.sin(t / 90 + rng.random()) + rng.normal(0, 0.5, seconds)
        cpu = np.clip(55 + 0.004 * t + rng.normal(0, 3.0, seconds), 0, 100)
        mem = 96 + rng.normal(0, 2.0, seconds)
        disk_temp = 38 + rng.normal(0, 0.4, seconds)
        net_io = 320 + latency * 2 + rng.normal(0, 12, seconds)
        power = 180 + cpu * 2.4 + net_io * 0.08
        df = pd.DataFrame(
            {
                "ts": t + 1_700_000_000,
                "service_id": service_id,
                "latency_ms": latency,
                "cpu_pct": cpu,
                "mem_used_gb": mem,
                "disk_temp_c": disk_temp,
                "net_io_mb_s": net_io,
                "power_w": power,
            }
        )
        # --- 埋脏点（可复现；用短样本（seconds 较小）时自动跳过越界埋点）---
        if seconds > 30:
            df.loc[30, "latency_ms"] = 5000.0  # 量程越界
        if seconds > 200:
            df.loc[200, "disk_temp_c"] += 18.0  # 孤立尖峰
        if service_id == "V002" and seconds > 500:
            df.loc[500:508, "disk_temp_c"] = 82.0  # 严重过热段（9s）
        if service_id == "V003" and seconds > 700:
            df = df[~df["ts"].between(1_700_000_000 + 700, 1_700_000_000 + 704)].copy()
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df = df.sample(frac=1, random_state=rng).reset_index(drop=True)  # 乱序到达
    return df


def write_platform_csv(df: pd.DataFrame, path: str | Path) -> Path:
    """把平台 DataFrame 写为 CSV（产物写 /tmp，仓库不落数据）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def read_platform(path: str | Path) -> pd.DataFrame:
    """读 CSV 并保留列顺序。"""
    df = pd.read_csv(path)
    missing = [c for c in PLATFORM_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"平台 CSV 缺少列：{missing}（应为 {PLATFORM_COLUMNS}）")
    return df[list(PLATFORM_COLUMNS)]
