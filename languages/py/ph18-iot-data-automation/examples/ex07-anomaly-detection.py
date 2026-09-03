#!/usr/bin/env python3
# examples/ex07-anomaly-detection.py —— AI 异常检测：Isolation Forest 落地（主文档 3.7）
# 验证环境：Python 3.13.12，numpy 2.5.2 / pandas 3.0.5 / scikit-learn 1.9.0
# 运行：python3 ex07-anomaly-detection.py（打印教学输出 + 断言自检，失败退出码非 0）
# 测试：python3 -m pytest ex07-anomaly-detection.py -q（收集 test_* 跑断言）
# lint：ruff check ex07-anomaly-detection.py
# 验证状态：已验证（Python 3.13.12 + scikit-learn 1.9.0 本机实测：自检与 pytest 全绿）
"""AI 异常检测：把 ph15 的 sklearn 技能落到「规则抓不住」的遥测异常上。

ex04 的规则引擎擅长已知模式（过热、SOC 骤降）；**未知/复合模式**要靠无监督异常检测。
本示例用 Isolation Forest 在特征上找离群——特征不是原始信号而是「信号 + 窗口形态
（滚动均值/标准差）」，让模型能识别"这段的形态不像平常"。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

# 异常埋点说明（与 label 列同步；fit 不使用 label —— 真正无监督）
ANOMALIES = {
    "V001": [],  # 健康车：作为"不应误报太多"的对照
    "V002": [("temp_excursion", 900, 940)],  # 40s 温度窜到 62℃（幅度不大、规则阈值 55 抓不到）
    "V003": [("stuck_signal", 1200, 1260)],  # 60s 车速冻结为 0 但功率照旧（传感器故障复合形态）
}


def generate_telemetry(seconds: int = 2000, seed: int = 21) -> pd.DataFrame:
    """自造 3 车遥测；按 ANOMALIES 埋入异常段，并给出 label 列用于事后评估。"""
    rng = np.random.default_rng(seed)
    t = np.arange(seconds, dtype=float)
    rows: list[pd.DataFrame] = []
    for vehicle_id, anomalies in ANOMALIES.items():
        temp = 32 + 3 * np.sin(t / 800) + rng.normal(0, 0.4, seconds)
        speed = 55 + 25 * np.sin(t / 120) + rng.normal(0, 0.5, seconds)
        current = -30 - speed / 8 + rng.normal(0, 1.5, seconds)
        voltage = 388 + 2 * np.sin(t / 1500) + rng.normal(0, 0.5, seconds)
        label = np.zeros(seconds, dtype=bool)
        for kind, start, end in anomalies:
            # 短测试（seconds < 异常埋点位置）时裁剪到有效区间，避免空切片广播错
            s, e = min(start, seconds), min(end, seconds)
            if e <= s:
                continue
            if kind == "temp_excursion":
                temp[s:e] = 62 + rng.normal(0, 0.3, e - s)
            elif kind == "stuck_signal":
                speed[s:e] = 0.0
            label[s:e] = True
        rows.append(
            pd.DataFrame(
                {
                    "ts": t + 1_700_000_000,
                    "vehicle_id": vehicle_id,
                    "speed_kmh": speed,
                    "soc_pct": np.clip(80 - t / 100, 0, 100),
                    "pack_voltage_v": voltage,
                    "pack_temp_c": temp,
                    "pack_current_a": current,
                    "power_kw": voltage * current / 1000,
                    "label": label,
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


FEATURE_COLS = ("speed_kmh", "pack_temp_c", "pack_current_a", "pack_voltage_v", "power_kw")
WINDOW = 20  # 形态特征窗口


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """特征矩阵：原始信号 + 20s 滚动均值/标准差（局部形态）。丢窗口前缀 NaN 行。"""
    frames: list[pd.DataFrame] = []
    for _vid, grp in df.groupby("vehicle_id", sort=False):
        g = grp.sort_values("ts")
        feats = g[list(FEATURE_COLS)].copy()  # 列索引要 list（tuple 会被当单个标签）
        for col in FEATURE_COLS:
            feats[f"{col}_mean{WINDOW}"] = g[col].rolling(WINDOW, min_periods=WINDOW).mean()
            feats[f"{col}_std{WINDOW}"] = g[col].rolling(WINDOW, min_periods=WINDOW).std()
        frames.append(feats)
    out = pd.concat(frames)
    # 把窗口前缀 NaN 行剔除（前 WINDOW-1 行无形态特征）
    return out.dropna().reset_index(drop=True)


def run_isolation_forest(features: pd.DataFrame, contamination: float = 0.05) -> np.ndarray:
    """训练并打分：返回每行的异常分（越大越异常，0 为校准阈值）。

    用 contamination 参数训练时，模型会把训练集里约 contamination 比例的样本校准为负分，
    所以 predict 阈值取 0 即可（而不是拍一个 -0.5 之类的经验值）。"""
    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=0,
    )
    model.fit(features)  # 无监督：fit 只用 X，不带 label
    return model.decision_function(features)  # 正常样本得分为正


def evaluate(df: pd.DataFrame, scores: np.ndarray, threshold: float = 0.0) -> dict[str, float]:
    """对照埋点 label 评估召回/误报（该 label 只用于评估，绝不进入训练）。"""
    # build_features 丢过窗口前缀行，需把 label 也裁剪到同一对齐
    all_labels: list[bool] = []
    for _vid, grp in df.groupby("vehicle_id", sort=False):
        g = grp.sort_values("ts")
        all_labels.extend(g["label"].iloc[WINDOW - 1 :].tolist())
    labels = np.asarray(all_labels, dtype=bool)
    assert len(labels) == len(scores)
    predicted = scores < threshold
    anomalies_total = int(labels.sum())
    detected = int((predicted & labels).sum())
    fp = int((predicted & ~labels).sum())
    return {
        "anomaly_rows": anomalies_total,
        "detected": detected,
        "recall": detected / anomalies_total if anomalies_total else 1.0,
        "fp": fp,
        "fp_rate": fp / int((~labels).sum()),
    }


def main() -> None:
    telemetry = generate_telemetry()
    features = build_features(telemetry)
    scores = run_isolation_forest(features)
    metrics = evaluate(telemetry, scores)

    print("== Isolation Forest 评估（对照埋点 label，仅评估用）==")
    for key, value in metrics.items():
        print(f"  {key}: {value:.4f}" if isinstance(value, float) else f"  {key}: {value}")

    # 自检：召回足够高、健康车 V001 误报可控
    assert metrics["recall"] >= 0.6, f"召回过低：{metrics['recall']:.3f}"
    assert metrics["fp_rate"] <= 0.15, f"误报率过高：{metrics['fp_rate']:.3f}"

    # 产物纪律：把分数并回原始帧写 /tmp（可接 Dashboard/告警通道）
    # 注意与 build_features 用同一套「去窗口前缀行」的对齐，否则长度对不上
    aligned: list[pd.DataFrame] = []
    for _vid, grp in telemetry.groupby("vehicle_id", sort=False):
        aligned.append(grp.sort_values("ts").iloc[WINDOW - 1 :])
    scored = pd.concat(aligned)
    assert len(scored) == len(scores)
    scored["anomaly_score"] = scores
    scored["flagged"] = scores < 0.0  # 校准阈值：负分 ≈ 离群
    out_dir = Path("/tmp/ph18-ex07")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "anomaly_scores.csv"
    scored.to_csv(out_csv, index=False)
    print(f"\n评分已写：{out_csv}（含 anomaly_score 与 flagged 列）")
    print("\n自检通过：召回 ≥ 0.6、误报率 ≤ 0.15、产物落盘")


def test_healthy_vehicle_low_fp() -> None:
    df = generate_telemetry(seconds=600, seed=3)
    # 只留 V001 与其后车（此时 ANOMALIES 仍给 V002/V003 埋点，只看 V001）
    v001 = df[df["vehicle_id"] == "V001"]
    feats = build_features(v001)
    scores = run_isolation_forest(feats)
    fp_rate = float((scores < 0.0).mean())
    assert fp_rate <= 0.08, f"健康车误报率过高：{fp_rate:.3f}"


def test_detector_finds_injected_temp_excursion() -> None:
    df = generate_telemetry(seconds=2000, seed=21)
    features = build_features(df)
    scores = run_isolation_forest(features)
    metrics = evaluate(df, scores)
    assert metrics["recall"] >= 0.6
    assert metrics["fp_rate"] <= 0.15


def test_build_features_drops_window_prefix() -> None:
    df = generate_telemetry(seconds=100, seed=1)
    features = build_features(df)
    # 3 车 × (100 - 19) = 243 行
    assert len(features) == 3 * (100 - (WINDOW - 1))
    assert not features.isna().any().any()


if __name__ == "__main__":
    main()
