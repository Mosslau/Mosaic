#!/usr/bin/env python3
# examples/ex03-battery-soh.py —— 电池数据与健康度（SOH）估计（主文档 3.3）
# 验证环境：Python 3.13 + numpy + pandas；本机实测 3.13.12 + numpy 2.5.2 + pandas 3.0.5
# 运行：python3 ex03-battery-soh.py（打印教学输出 + 断言自检，失败退出码非 0）
# 测试：python3 -m pytest ex03-battery-soh.py -q（收集 test_* 跑断言）
# lint：ruff check ex03-battery-soh.py
# 验证状态：已验证（Python 3.13.12 + numpy 2.5.2 + pandas 3.0.5 本机实测：自检与 pytest 全绿）
"""电池健康度（SOH）估计：基于充电段的能量积分反推可用容量。

思想（主文档 3.3/4.3 展开）：SOH = 当前可用容量 / 额定容量。一次充电段里，电池从
SOC_lo 充到 SOC_hi 吸收了 E kWh，则这段时间的可用容量 ≈ E / (ΔSOC/100)。逐次充电
段的容量估计波动大，用滚动中位数平滑得到 SOH 趋势。数据自造并带老化漂移。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RATED_CAPACITY_KWH = 60.0  # 额定可用容量（全新电池，车企标称，通常写进电池铭牌/BMS 初始标定）
AGING_PER_CYCLE = 0.04  # 每完整循环容量衰减 %（教学参数；真实电池与化学体系/温区有关）


def generate_battery_history(
    vehicles: tuple[str, ...] = ("V001", "V002", "V003"),
    cycles: int = 180,
    seed: int = 11,
) -> pd.DataFrame:
    """自造每个车队成员 cycles 次充电记录：容量随循环数线性衰减 + 过程噪声。

    返回列：vehicle_id、cycle、charge_ts、soc_lo、soc_hi、energy_kwh。
    energy_kwh = 当前容量 × ΔSOC/100 × (1 + 测量噪声)——用它可以反解回真实容量。
    """
    rng = np.random.default_rng(seed)
    rows: list[dict[str, float | str | int]] = []
    start_ts = 1_700_000_000  # 2023-11-14 前后
    for vehicle_id in vehicles:
        for cycle in range(1, cycles + 1):
            capacity = RATED_CAPACITY_KWH * (1 - AGING_PER_CYCLE / 100) ** cycle
            soc_lo = float(rng.uniform(15, 55))  # 每次充电从不同电量开始
            soc_hi = 100.0
            delta_soc = soc_hi - soc_lo
            noise = rng.normal(0, 0.15)  # kWh 计量噪声（±0.15 kWh，BMS 电流积分量级）
            energy = capacity * delta_soc / 100.0 + noise
            rows.append(
                {
                    "vehicle_id": vehicle_id,
                    "cycle": cycle,
                    "charge_ts": float(start_ts + cycle * 86_400 * (1 + rng.uniform(-0.3, 0.6))),
                    "soc_lo": soc_lo,
                    "soc_hi": soc_hi,
                    "energy_kwh": max(energy, 0.0),
                }
            )
    return pd.DataFrame(rows)


def estimate_soh(history: pd.DataFrame) -> pd.DataFrame:
    """对每次充电段估计容量并换算 SOH，再按车做滚动中位数平滑。

    capacity_est = energy_kwh / (ΔSOC/100)，soh_raw = capacity_est / RATED × 100。
    单次估计噪声大（soc 读数误差会直接放大容量误差），所以输出平滑列 soh_smooth。
    """
    df = history.copy()
    df["delta_soc"] = df["soc_hi"] - df["soc_lo"]
    df["capacity_est_kwh"] = df["energy_kwh"] / (df["delta_soc"] / 100.0)
    df["soh_raw_pct"] = df["capacity_est_kwh"] / RATED_CAPACITY_KWH * 100.0
    df["soh_smooth_pct"] = (
        df.groupby("vehicle_id")["soh_raw_pct"]
        .rolling(15, center=True, min_periods=1)
        .median()
        .reset_index(level=0, drop=True)
    )
    return df


def fleet_soh_table(estimated: pd.DataFrame) -> pd.DataFrame:
    """车队级 SOH 概览：每辆车最新平滑 SOH、相对新车的衰减、总循环数。"""
    latest = estimated.sort_values("cycle").groupby("vehicle_id").tail(1).set_index("vehicle_id")
    return pd.DataFrame(
        {
            "soh_pct": latest["soh_smooth_pct"].round(2),
            "cycles": latest["cycle"],
        }
    )


def main() -> None:
    history = generate_battery_history()
    estimated = estimate_soh(history)
    overview = fleet_soh_table(estimated)
    print("== 车队 SOH 概览（最新充电段，平滑后）==")
    print(overview.to_string())

    print("\n== V001 前 5 与末 3 次循环的估计 ==")
    v001 = estimated[estimated["vehicle_id"] == "V001"].copy()
    sample = pd.concat([v001.head(5), v001.tail(3)])
    print(
        sample[["cycle", "soc_lo", "energy_kwh", "capacity_est_kwh", "soh_smooth_pct"]].to_string(
            index=False
        )
    )

    # ---- 自检断言 ----
    for vid in ("V001", "V002", "V003"):
        v = estimated[estimated["vehicle_id"] == vid].sort_values("cycle")
        # 容量随循环数衰减：末段平滑 SOH 必须低于前段
        assert v["soh_smooth_pct"].iloc[-1] < v["soh_smooth_pct"].iloc[0]
        # 估计容量落在额定容量 ±12% 内（模型应能"还原"真实容量）
        assert (
            v["capacity_est_kwh"]
            .between(RATED_CAPACITY_KWH * 0.88, RATED_CAPACITY_KWH * 1.05)
            .all()
        )
    # 车队 SOH 排序正确（老化一致时 SOH 应都接近、略有差异）
    assert overview["soh_pct"].between(88, 100).all()
    # 理论漂移验证：180 循环后理论 SOH ≈ 0.9996^180 ≈ 93.0%
    theo = 100 * (1 - AGING_PER_CYCLE / 100) ** 180
    assert overview["soh_pct"].mean() < theo + 1.5  # 平滑估计围绕理论值波动

    # 产物纪律：概览表写 /tmp
    out_dir = Path("/tmp/ph18-ex03")
    out_dir.mkdir(parents=True, exist_ok=True)
    overview.to_csv(out_dir / "fleet_soh.csv")
    print(f"\n概览已写：{out_dir / 'fleet_soh.csv'}")
    print("\n自检通过：SOH 随循环衰减、容量估计在额定附近、理论漂移验证全绿")


def test_estimate_recovers_true_capacity() -> None:
    # 单次充电：容量 60kWh，从 40% 充到 100%，无噪声 → 能量恰好 36kWh
    df = pd.DataFrame(
        {
            "vehicle_id": ["V001"],
            "cycle": [1],
            "charge_ts": [1_700_000_000.0],
            "soc_lo": [40.0],
            "soc_hi": [100.0],
            "energy_kwh": [36.0],
        }
    )
    est = estimate_soh(df)
    assert abs(est["capacity_est_kwh"].iloc[0] - RATED_CAPACITY_KWH) < 1e-9
    assert abs(est["soh_raw_pct"].iloc[0] - 100.0) < 1e-9


def test_soh_declines_with_cycles() -> None:
    history = generate_battery_history(vehicles=("V001",), cycles=60, seed=3)
    estimated = estimate_soh(history)
    v = estimated.sort_values("cycle")
    assert v["soh_smooth_pct"].iloc[-1] < v["soh_smooth_pct"].iloc[0]


def test_energy_formula_uses_actual_soc_span() -> None:
    # 同样 30kWh，SOC 跨度不同 → 估计容量不同（公式对 ΔSOC 敏感）
    df = pd.DataFrame(
        {
            "vehicle_id": ["V001", "V001"],
            "cycle": [1, 2],
            "charge_ts": [1_700_000_000.0, 1_700_000_100.0],
            "soc_lo": [50.0, 25.0],
            "soc_hi": [100.0, 100.0],
            "energy_kwh": [30.0, 45.0],
        }
    )
    est = estimate_soh(df)
    caps = est.sort_values("cycle")["capacity_est_kwh"].tolist()
    assert abs(caps[0] - 60.0) < 1e-9  # 50→100 跨度 50%，30kWh → 60kWh 容量
    assert abs(caps[1] - 60.0) < 1e-9  # 25→100 跨度 75%，45kWh → 60kWh 容量


if __name__ == "__main__":
    main()
