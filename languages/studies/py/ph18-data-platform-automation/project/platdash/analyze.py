# project/platdash/analyze.py —— 平台/单实例分析（纯函数，便于单测）
# 验证环境：Python 3.13 + pandas；本机实测 Python 3.13.9 + pandas（见 README 验收标准）
"""分析层：把清洗后的 DataFrame 变成平台/单实例统计。

全为纯函数（输入 df、输出 dict），不碰文件/图表 → 报表层与 CLI 之外的任何消费方
（FastAPI、BI）都能复用同一份数字。数据传输量按「网络入出速率 × 时间积分」估算，
耗电量按「功率积分」估算（教学近似，指标口径在真实平台由计量口径决定）。
"""

from __future__ import annotations

import pandas as pd

MAX_DT_S = 2.0  # 积分时对 >2s 的掉点按 0 处理（避免把缺口当持续速率）

_TRAFFIC_DIVISOR = 1024.0  # MB/s × s → GB（按 1024 换算，教学约定）
_ENERGY_DIVISOR = 3600.0  # W × s → kWh


def service_summary(
    df: pd.DataFrame, service_id: str | None = None
) -> dict[str, float | int | str]:
    """单实例摘要：若 df 为单实例则 service_id 可省；多实例则必须给 service_id。"""
    if service_id is not None:
        part = df[df["service_id"] == service_id]
    else:
        part = df
    if part.empty:
        raise ValueError(f"没有 {service_id or '该服务实例'} 的数据")
    part = part.sort_values("ts")
    ts = part["ts"].to_numpy()
    dt = pd.Series(ts).diff().fillna(1.0).to_numpy()
    dt = dt.clip(0.0, MAX_DT_S)  # 掉点 >2s 不计入积分
    traffic_gb = float((part["net_io_mb_s"].to_numpy() * dt).sum() / _TRAFFIC_DIVISOR)
    energy_kwh = float((part["power_w"].to_numpy() * dt).sum() / _ENERGY_DIVISOR)
    duration_s = float(part["ts"].max() - part["ts"].min())
    latency = part["latency_ms"].to_numpy()
    return {
        "service_id": part["service_id"].iloc[0] if service_id is None else service_id,
        "points": int(len(part)),
        "duration_h": round(duration_s / 3600.0, 3),
        "traffic_gb": round(traffic_gb, 1),
        "energy_kwh": round(energy_kwh, 1),
        "mean_latency_ms": round(float(latency.mean()), 1),
        "p95_latency_ms": round(float(pd.Series(latency).quantile(0.95)), 1),
        "max_cpu_pct": round(float(part["cpu_pct"].max()), 1),
        "mean_disk_temp_c": round(float(part["disk_temp_c"].mean()), 1),
        "hot_seconds": int((part["disk_temp_c"] > 75.0).sum()),
    }


def platform_summary(df: pd.DataFrame) -> dict[str, object]:
    """平台摘要 + 按实例表格数据（rows 供报表层直接渲染）。"""
    services = sorted(df["service_id"].unique())
    per_service = [service_summary(df, sid) for sid in services]
    total_traffic = sum(v["traffic_gb"] for v in per_service)
    total_energy = sum(v["energy_kwh"] for v in per_service)
    platform: dict[str, object] = {
        "services": services,
        "total_points": int(len(df)),
        "total_traffic_gb": round(float(total_traffic), 1),
        "total_energy_kwh": round(float(total_energy), 1),
        "rows": per_service,
    }
    return platform


def platform_table(df: pd.DataFrame) -> pd.DataFrame:
    """按实例汇总表（DataFrame），report/cli 复用。"""
    platform = platform_summary(df)
    return pd.DataFrame(platform["rows"])
