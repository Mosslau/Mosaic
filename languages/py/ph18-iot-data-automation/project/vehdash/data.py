# project/vehdash/data.py —— 车队遥测样例生成与读取
# 验证环境：Python 3.13 + numpy/pandas；本机实测 Python 3.13.12 + pandas 3.0.5
"""确定性车队样例数据（教学用）：3 车 × 20 分钟 1Hz 遥测 + 刻意埋的脏点。

脏点设计（保证清洗/分析有活干、断言可写）：
- 每车在固定时刻有 1 个速度越界点（300 km/h）与 1 个孤立温度尖峰
- V002 有一段持续过热（45℃+，>55℃ 的"严重过热"刻意安排 8s）
- V003 有一段小缺口（4s 掉点）
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# 列 schema（与 examples/ex02、主文档 3.2 一致；全阶段共用一份）
FLEET_COLUMNS = (
    "ts",
    "vehicle_id",
    "speed_kmh",
    "soc_pct",
    "pack_voltage_v",
    "pack_temp_c",
    "pack_current_a",
    "power_kw",
)

# 量程规格（与清洗共用，纯函数模块间以常量形式共享）
RANGES: dict[str, tuple[float, float]] = {
    "speed_kmh": (0.0, 220.0),
    "soc_pct": (0.0, 100.0),
    "pack_voltage_v": (250.0, 420.0),
    "pack_temp_c": (-40.0, 65.0),
    "pack_current_a": (-300.0, 400.0),
    "power_kw": (-300.0, 300.0),
}


def generate_fleet(
    vehicles: tuple[str, ...] = ("V001", "V002", "V003"),
    minutes: int = 20,
    seed: int = 17,
) -> pd.DataFrame:
    """生成车队遥测（未清洗：乱序 + 埋点），与文件解耦，便于测试直接用 DataFrame。"""
    rng = np.random.default_rng(seed)
    seconds = minutes * 60
    t = np.arange(seconds, dtype=float)
    frames: list[pd.DataFrame] = []
    for vehicle_id in vehicles:
        base_speed = {"V001": 50, "V002": 45, "V003": 60}[vehicle_id]
        speed = base_speed + 15 * np.sin(t / 90 + rng.random()) + rng.normal(0, 0.5, seconds)
        temp = 30 + rng.normal(0, 0.4, seconds)
        soc = np.clip(85 - 0.004 * t + rng.normal(0, 0.08, seconds), 0, 100)
        voltage = 388 + rng.normal(0, 0.6, seconds)
        current = -25 - speed / 10 + rng.normal(0, 1.2, seconds)
        df = pd.DataFrame(
            {
                "ts": t + 1_700_000_000,
                "vehicle_id": vehicle_id,
                "speed_kmh": speed,
                "soc_pct": soc,
                "pack_voltage_v": voltage,
                "pack_temp_c": temp,
                "pack_current_a": current,
                "power_kw": voltage * current / 1000.0,
            }
        )
        # --- 埋脏点（可复现；用短样本（seconds 较小）时自动跳过越界埋点）---
        if seconds > 30:
            df.loc[30, "speed_kmh"] = 300.0  # 物理越界
        if seconds > 200:
            df.loc[200, "pack_temp_c"] += 18.0  # 孤立尖峰
        if vehicle_id == "V002" and seconds > 500:
            df.loc[500:508, "pack_temp_c"] = 57.0  # 严重过热段（9s）
        if vehicle_id == "V003" and seconds > 700:
            df = df[~df["ts"].between(1_700_000_000 + 700, 1_700_000_000 + 704)].copy()
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df = df.sample(frac=1, random_state=rng).reset_index(drop=True)  # 乱序到达
    return df


def write_fleet_csv(df: pd.DataFrame, path: str | Path) -> Path:
    """把车队 DataFrame 写为 CSV（产物写 /tmp，仓库不落数据）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def read_fleet(path: str | Path) -> pd.DataFrame:
    """读 CSV 并保留列顺序。"""
    df = pd.read_csv(path)
    missing = [c for c in FLEET_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"车队 CSV 缺少列：{missing}（应为 {FLEET_COLUMNS}）")
    return df[list(FLEET_COLUMNS)]
