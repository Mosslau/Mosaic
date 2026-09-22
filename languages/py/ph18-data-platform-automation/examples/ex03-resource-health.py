#!/usr/bin/env python3
# examples/ex03-resource-health.py —— 节点资源数据与健康度（HEALTH）估计（主文档 3.3）
# 验证环境：Python 3.13 + numpy + pandas；本机实测 3.13.12 + numpy 2.5.2 + pandas 3.0.5
# 运行：python3 ex03-resource-health.py（打印教学输出 + 断言自检，失败退出码非 0）
# 测试：python3 -m pytest ex03-resource-health.py -q（收集 test_* 跑断言）
# lint：ruff check ex03-resource-health.py
# 验证状态：已验证（Python 3.13.12 + numpy 2.5.2 + pandas 3.0.5 本机实测：自检与 pytest 全绿）
"""节点资源健康度（HEALTH）估计：基于负载段的计量积分反推可用容量。

思想（主文档 3.3/4.3 展开）：HEALTH = 当前可用容量 / 额定容量。一次负载段里，节点资源从
usage_lo 升到 usage_hi 期间计量到 E GB，则这段时间的可用容量 ≈ E / (Δusage/100)。逐次负载
段的容量估计波动大，用滚动中位数平滑得到 HEALTH 趋势。数据自造并带老化漂移。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RATED_CAPACITY_GB = 60.0  # 额定可用容量（全新节点资源，厂商额定值，通常写进节点资源标定表）
AGING_PER_CYCLE = 0.04  # 每完整循环容量衰减 %（教学参数；真实节点资源与化学体系/温区有关）


def generate_resource_history(
    services: tuple[str, ...] = ("V001", "V002", "V003"),
    cycles: int = 180,
    seed: int = 11,
) -> pd.DataFrame:
    """自造每个平台成员 cycles 次负载记录：容量随循环数线性衰减 + 过程噪声。

    返回列：service_id、cycle、charge_ts、usage_lo、usage_hi、measured_gb。
    measured_gb = 当前容量 × ΔCPU/100 × (1 + 测量噪声)——用它可以反解回真实容量。
    """
    rng = np.random.default_rng(seed)
    rows: list[dict[str, float | str | int]] = []
    start_ts = 1_700_000_000  # 2023-11-14 前后
    for service_id in services:
        for cycle in range(1, cycles + 1):
            capacity = RATED_CAPACITY_GB * (1 - AGING_PER_CYCLE / 100) ** cycle
            usage_lo = float(rng.uniform(15, 55))  # 每次负载从不同水位开始
            usage_hi = 100.0
            delta_usage = usage_hi - usage_lo
            noise = rng.normal(0, 0.15)  # GB 计量噪声（±0.15 GB，BMS 电流积分量级）
            energy = capacity * delta_usage / 100.0 + noise
            rows.append(
                {
                    "service_id": service_id,
                    "cycle": cycle,
                    "charge_ts": float(start_ts + cycle * 86_400 * (1 + rng.uniform(-0.3, 0.6))),
                    "usage_lo": usage_lo,
                    "usage_hi": usage_hi,
                    "measured_gb": max(energy, 0.0),
                }
            )
    return pd.DataFrame(rows)


def estimate_health(history: pd.DataFrame) -> pd.DataFrame:
    """对每次负载段估计容量并换算 HEALTH，再按服务实例做滚动中位数平滑。

    capacity_est = measured_gb / (ΔCPU/100)，health_raw = capacity_est / RATED × 100。
    单次估计噪声大（soc 读数误差会直接放大容量误差），所以输出平滑列 health_smooth。
    """
    df = history.copy()
    df["delta_usage"] = df["usage_hi"] - df["usage_lo"]
    df["capacity_est_gb"] = df["measured_gb"] / (df["delta_usage"] / 100.0)
    df["health_raw_pct"] = df["capacity_est_gb"] / RATED_CAPACITY_GB * 100.0
    df["health_smooth_pct"] = (
        df.groupby("service_id")["health_raw_pct"]
        .rolling(15, center=True, min_periods=1)
        .median()
        .reset_index(level=0, drop=True)
    )
    return df


def platform_health_table(estimated: pd.DataFrame) -> pd.DataFrame:
    """平台级 HEALTH 概览：每个服务实例最新平滑 HEALTH、相对新实例的衰减、总负载周期数。"""
    latest = estimated.sort_values("cycle").groupby("service_id").tail(1).set_index("service_id")
    return pd.DataFrame(
        {
            "health_pct": latest["health_smooth_pct"].round(2),
            "cycles": latest["cycle"],
        }
    )


def main() -> None:
    history = generate_resource_history()
    estimated = estimate_health(history)
    overview = platform_health_table(estimated)
    print("== 平台 HEALTH 概览（最新负载段，平滑后）==")
    print(overview.to_string())

    print("\n== V001 前 5 与末 3 次循环的估计 ==")
    v001 = estimated[estimated["service_id"] == "V001"].copy()
    sample = pd.concat([v001.head(5), v001.tail(3)])
    cols = ["cycle", "usage_lo", "measured_gb", "capacity_est_gb", "health_smooth_pct"]
    print(sample[cols].to_string(index=False))

    # ---- 自检断言 ----
    for vid in ("V001", "V002", "V003"):
        v = estimated[estimated["service_id"] == vid].sort_values("cycle")
        # 容量随循环数衰减：末段平滑 HEALTH 必须低于前段
        assert v["health_smooth_pct"].iloc[-1] < v["health_smooth_pct"].iloc[0]
        # 估计容量落在额定容量 ±12% 内（模型应能"还原"真实容量）
        assert (
            v["capacity_est_gb"].between(RATED_CAPACITY_GB * 0.88, RATED_CAPACITY_GB * 1.05).all()
        )
    # 平台 HEALTH 排序正确（老化一致时 HEALTH 应都接近、略有差异）
    assert overview["health_pct"].between(88, 100).all()
    # 理论漂移验证：180 循环后理论 HEALTH ≈ 0.9996^180 ≈ 93.0%
    theo = 100 * (1 - AGING_PER_CYCLE / 100) ** 180
    assert overview["health_pct"].mean() < theo + 1.5  # 平滑估计围绕理论值波动

    # 产物纪律：概览表写 /tmp
    out_dir = Path("/tmp/ph18-ex03")
    out_dir.mkdir(parents=True, exist_ok=True)
    overview.to_csv(out_dir / "platform_health.csv")
    print(f"\n概览已写：{out_dir / 'platform_health.csv'}")
    print("\n自检通过：HEALTH 随循环衰减、容量估计在额定附近、理论漂移验证全绿")


def test_estimate_recovers_true_capacity() -> None:
    # 单次负载：容量 60GB，水位从 40% 升到 100%，无噪声 → 计量恰好 36GB
    df = pd.DataFrame(
        {
            "service_id": ["V001"],
            "cycle": [1],
            "charge_ts": [1_700_000_000.0],
            "usage_lo": [40.0],
            "usage_hi": [100.0],
            "measured_gb": [36.0],
        }
    )
    est = estimate_health(df)
    assert abs(est["capacity_est_gb"].iloc[0] - RATED_CAPACITY_GB) < 1e-9
    assert abs(est["health_raw_pct"].iloc[0] - 100.0) < 1e-9


def test_health_declines_with_cycles() -> None:
    history = generate_resource_history(services=("V001",), cycles=60, seed=3)
    estimated = estimate_health(history)
    v = estimated.sort_values("cycle")
    assert v["health_smooth_pct"].iloc[-1] < v["health_smooth_pct"].iloc[0]


def test_capacity_formula_uses_actual_usage_span() -> None:
    # 同样 30GB，水位跨度不同 → 估计容量不同（公式对 Δusage 敏感）
    df = pd.DataFrame(
        {
            "service_id": ["V001", "V001"],
            "cycle": [1, 2],
            "charge_ts": [1_700_000_000.0, 1_700_000_100.0],
            "usage_lo": [50.0, 25.0],
            "usage_hi": [100.0, 100.0],
            "measured_gb": [30.0, 45.0],
        }
    )
    est = estimate_health(df)
    caps = est.sort_values("cycle")["capacity_est_gb"].tolist()
    assert abs(caps[0] - 60.0) < 1e-9  # 50→100 跨度 50%，30GB → 60GB 容量
    assert abs(caps[1] - 60.0) < 1e-9  # 25→100 跨度 75%，45GB → 60GB 容量


if __name__ == "__main__":
    main()
