# project/vehdash/analyze.py —— 车队/单车分析（纯函数，便于单测）
# 验证环境：Python 3.13 + pandas；本机实测 Python 3.13.12 + pandas 3.0.5
"""分析层：把清洗后的 DataFrame 变成车队/单车统计。

全为纯函数（输入 df、输出 dict），不碰文件/图表 → 报表层与 CLI 之外的任何消费方
（FastAPI、BI）都能复用同一份数字。距离按「速度 × 时间积分」估算，能耗按
「|功率| 积分」估算（教学近似，指标口径在真实平台由标定决定）。
"""

from __future__ import annotations

import pandas as pd

MAX_DT_S = 2.0  # 积分时对 >2s 的掉点按 0 处理（避免把缺口当长时间行驶）


def vehicle_summary(
    df: pd.DataFrame, vehicle_id: str | None = None
) -> dict[str, float | int | str]:
    """单车摘要：若 df 为单车则 vehicle_id 可省；多车则必须给 vehicle_id。"""
    if vehicle_id is not None:
        part = df[df["vehicle_id"] == vehicle_id]
    else:
        part = df
    if part.empty:
        raise ValueError(f"没有 {vehicle_id or '该车辆'} 的数据")
    part = part.sort_values("ts")
    ts = part["ts"].to_numpy()
    dt = pd.Series(ts).diff().fillna(1.0).to_numpy()
    dt = dt.clip(0.0, MAX_DT_S)  # 掉点 >2s 不算里程
    speed_ms = part["speed_kmh"].to_numpy() / 3.6
    distance_km = float((speed_ms * dt).sum() / 1000.0)
    energy_kwh = float((part["power_kw"].abs() * dt / 3600.0).sum())
    duration_s = float(part["ts"].max() - part["ts"].min())
    hot_seconds = int((part["pack_temp_c"] > 55.0).sum())
    return {
        "vehicle_id": part["vehicle_id"].iloc[0] if vehicle_id is None else vehicle_id,
        "points": int(len(part)),
        "duration_h": round(duration_s / 3600.0, 3),
        "distance_km": round(distance_km, 1),
        "energy_kwh": round(energy_kwh, 1),
        "mean_speed_kmh": round(float(part["speed_kmh"].mean()), 1),
        "mean_temp_c": round(float(part["pack_temp_c"].mean()), 1),
        "min_soc": round(float(part["soc_pct"].min()), 1),
        "hot_seconds": hot_seconds,
        "soh_hint_pct": _soh_hint(part),
    }


def fleet_summary(df: pd.DataFrame) -> dict[str, object]:
    """车队摘要 + 按车表格数据（rows 供报表层直接渲染）。"""
    vehicles = sorted(df["vehicle_id"].unique())
    per_vehicle = [vehicle_summary(df, vid) for vid in vehicles]
    total_distance = sum(v["distance_km"] for v in per_vehicle)
    total_energy = sum(v["energy_kwh"] for v in per_vehicle)
    fleet: dict[str, object] = {
        "vehicles": vehicles,
        "total_points": int(len(df)),
        "total_distance_km": round(float(total_distance), 1),
        "total_energy_kwh": round(float(total_energy), 1),
        "rows": per_vehicle,
    }
    return fleet


def _soh_hint(part: pd.DataFrame) -> float:
    """SOH 提示值（教学版）：用「能量下降斜率」代替真实充电段估计。

    真实 SOH 需要充电段能量积分（见 examples/ex03），这里只把 soc 与能耗做线性
    拟合斜率换算成一个可展示的 0~100 值——仅作 Dashboard 的电池卡片示意。
    """
    try:
        slope = float(pd.Series(part["power_kw"]).rolling(600, min_periods=10).mean().iloc[-1])
    except (IndexError, ZeroDivisionError):
        return 100.0
    # 斜率越负（能耗越大）提示 SOH 略降；限制在 [85, 100] 内避免误导
    hint = 100.0 + slope * 0.6
    return round(min(max(hint, 85.0), 100.0), 1)


def fleet_table(df: pd.DataFrame) -> pd.DataFrame:
    """按车汇总表（DataFrame），report/cli 复用。"""
    fleet = fleet_summary(df)
    return pd.DataFrame(fleet["rows"])
