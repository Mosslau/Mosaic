# project/tests/test_telemetry.py —— 离线测试：清洗 / 统计 / 导出 / CLI 演示
# 运行（在 project/ 目录下）：pytest -q（已验证，5 个用例全过，不依赖网络）
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 导入平级的 telemetry_analyzer.py

from telemetry_analyzer import analyze, clean, export_report, generate_demo_data, main  # noqa: E402


def test_demo_data_three_vehicles():
    df = generate_demo_data()
    assert df["vehicle_id"].nunique() == 3
    assert {"vehicle_id", "time", "speed", "mileage", "energy"} <= set(df.columns)
    # 注入的缺陷数量与位置要能被 clean() 全量处理
    assert int(df["speed"].isna().sum()) == 3


def test_clean_fills_missing_and_removes_outliers():
    raw = generate_demo_data()
    cleaned = clean(raw)
    # 缺失值被组内中位数填充
    assert not cleaned["speed"].isna().any()
    # 异常值（320 / 280 km/h）被物理范围过滤
    assert cleaned["speed"].between(0, 200).all()
    # 2 个异常值被剔除，缺失行被填充后保留
    assert len(raw) - len(cleaned) == 2
    # 入参不被改动（复制语义）
    assert int(raw["speed"].isna().sum()) == 3


def test_analyze_computes_energy_per_100km():
    df = pd.DataFrame(
        {
            "vehicle_id": ["V001", "V001", "V001"],
            "time": pd.to_datetime(["2024-06-01 08:00:00", "2024-06-01 08:00:30", "2024-06-01 08:01:00"]),
            "speed": [60.0, 60.0, 60.0],
            "mileage": [10.0, 20.0, 30.0],  # 总里程 60
            "energy": [1.8, 3.6, 5.4],  # 总能耗 10.8 → 18 kWh/100km
        }
    )
    stats = analyze(df)
    assert stats.loc[0, "trips"] == 3
    assert stats.loc[0, "total_mileage"] == 60.0
    assert stats.loc[0, "total_energy"] == 10.8
    assert stats.loc[0, "avg_speed"] == 60.0
    assert np.isclose(stats.loc[0, "energy_per_100km"], 18.0)


def test_export_report_writes_files(tmp_path):
    cleaned = clean(generate_demo_data())
    stats = analyze(cleaned)
    files = export_report(stats, cleaned, tmp_path)
    assert len(files) == 2
    for f in files:
        assert f.exists() and f.stat().st_size > 0
    md = tmp_path / "telemetry_report.md"
    assert "按车辆汇总" in md.read_text(encoding="utf-8")


def test_main_demo_offline(tmp_path, capsys):
    assert main(["--demo", "-o", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "按车辆分组统计" in out
    assert (tmp_path / "speed_trend.png").exists()
    assert (tmp_path / "vehicle_compare.png").exists()
    assert (tmp_path / "telemetry_report.xlsx").exists()
