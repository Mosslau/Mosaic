# project/tests/test_metrics.py —— 离线测试：清洗 / 统计 / 导出 / CLI 演示
# 运行（在 project/ 目录下）：python3 -m pytest tests -q（离线，不依赖网络）
# 验证状态：已验证 —— python3 -m pytest tests -q -p no:cacheprovider：5 passed（离线，不依赖网络）
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 导入平级的 metrics_analyzer.py

from metrics_analyzer import (  # noqa: E402
    PLATFORM_COLUMNS,
    analyze,
    clean,
    export_report,
    generate_demo_data,
    main,
)


def test_demo_data_three_services():
    df = generate_demo_data()
    assert df["service_id"].nunique() == 3
    assert set(PLATFORM_COLUMNS) <= set(df.columns)
    # 注入的缺陷数量要能被 clean() 全量处理
    assert int(df["latency_ms"].isna().sum()) == 3


def test_clean_fills_missing_and_removes_outliers():
    raw = generate_demo_data()
    cleaned = clean(raw)
    # 缺失值被组内中位数填充
    assert not cleaned["latency_ms"].isna().any()
    # 越界延迟（5000 / 3000 ms）被物理量程过滤
    assert cleaned["latency_ms"].between(0, 2000).all()
    # 2 个越界值被剔除，3 个缺失行被填充后保留
    assert len(raw) - len(cleaned) == 2
    # 入参不被改动（复制语义）
    assert int(raw["latency_ms"].isna().sum()) == 3


def test_analyze_computes_metrics():
    df = pd.DataFrame(
        {
            "ts": pd.to_datetime(
                ["2024-06-01 08:00:00", "2024-06-01 08:00:30", "2024-06-01 08:01:00"]
            ),
            "service_id": ["S001", "S001", "S001"],
            "latency_ms": [40.0, 50.0, 60.0],
            "cpu_pct": [60.0, 70.0, 80.0],
            "mem_used_gb": [64.0, 96.0, 128.0],
            "disk_temp_c": [36.0, 37.0, 38.0],
            "net_io_mb_s": [300.0, 320.0, 340.0],
            "power_w": [200.0, 250.0, 300.0],
        }
    )
    stats = analyze(df)
    assert stats.loc[0, "samples"] == 3
    assert stats.loc[0, "avg_latency_ms"] == 50.0  # (40+50+60)/3
    assert stats.loc[0, "max_latency_ms"] == 60.0
    assert stats.loc[0, "max_mem_used_gb"] == 128.0
    assert np.isclose(stats.loc[0, "mem_peak_pct"], 50.0)  # 128 / 256 × 100


def test_export_report_writes_files(tmp_path):
    cleaned = clean(generate_demo_data())
    stats = analyze(cleaned)
    files = export_report(stats, cleaned, tmp_path)
    assert len(files) == 2
    for f in files:
        assert f.exists() and f.stat().st_size > 0
    md = tmp_path / "metrics_report.md"
    assert "按服务实例汇总" in md.read_text(encoding="utf-8")


def test_main_demo_offline(tmp_path, capsys):
    assert main(["--demo", "-o", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "按服务实例分组统计" in out
    assert (tmp_path / "latency_trend.png").exists()
    assert (tmp_path / "service_compare.png").exists()
    assert (tmp_path / "metrics_report.xlsx").exists()
