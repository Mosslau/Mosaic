# project/tests/test_platdash.py —— platdash 测试套件
# 验证环境：Python 3.13 + pytest + pandas + matplotlib；本机实测见 README 验收标准
"""9 个用例：清洗计数 / 传输量估算 / 过热检测 / 延迟分位 / 报告产物 / CLI 冒烟 / 缺列校验。"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from platdash.analyze import platform_summary, platform_table, service_summary
from platdash.clean import clean_platform
from platdash.cli import cmd_dashboard, cmd_summary
from platdash.data import generate_platform
from platdash.report import build_dashboard


def _scratch_dir(name: str) -> Path:
    """本测试的产物目录：写 /tmp（受限沙箱里对 pytest tmp_path 的逐层 mkdir 不稳定）。"""
    path = Path("/tmp/ph18-project-tests") / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _service_df(net_io: float, seconds: int = 100, sid: str = "V001") -> pd.DataFrame:
    t = pd.Series(range(seconds), dtype=float)
    return pd.DataFrame(
        {
            "ts": t + 1_700_000_000,
            "service_id": sid,
            "latency_ms": 80.0,
            "cpu_pct": 55.0,
            "mem_used_gb": 96.0,
            "disk_temp_c": 38.0,
            "net_io_mb_s": float(net_io),
            "power_w": 340.0,
        }
    )


def test_clean_removes_injected_anomalies() -> None:
    df = generate_platform(services=("V001", "V002", "V003"), minutes=10, seed=5)
    cleaned, stats = clean_platform(df)
    assert stats.phys_removed["latency_ms"] == 3  # 每实例一个 5000 ms 越界点
    assert stats.spike_removed["disk_temp_c"] == 3  # 每实例一个 +18℃ 单点尖峰
    assert (cleaned["latency_ms"] <= 2000).all()
    # 三个尖峰都在 ts=200 的那一秒 → 清洗后该时刻无残留行（过热段 82℃ 属持续事件，保留）
    assert cleaned[cleaned["ts"] == 1_700_000_200].empty


def test_service_summary_traffic_estimation() -> None:
    # 500 MB/s × 100s ÷ 1024 ≈ 48.8 GB（含首行 dt=1s，尾部缺 dt → 有效积分约 99~100 段）
    df = _service_df(net_io=500.0, seconds=100)
    summary = service_summary(df)
    assert summary["points"] == 100
    assert abs(summary["traffic_gb"] - (500.0 * 99) / 1024.0) < 5.0


def test_hot_seconds_only_on_overheating_service() -> None:
    df = generate_platform(services=("V001", "V002", "V003"), minutes=10, seed=5)
    cleaned, _ = clean_platform(df)
    v002 = service_summary(cleaned, "V002")
    v001 = service_summary(cleaned, "V001")
    assert v002["hot_seconds"] >= 6  # 埋了 9s 82℃ 过热段
    assert v001["hot_seconds"] == 0


def test_p95_latency_in_plausible_range() -> None:
    summary = service_summary(_service_df(net_io=400.0, seconds=600))
    assert 70.0 <= summary["p95_latency_ms"] <= 90.0


def test_platform_summary_rows_match_services() -> None:
    df = generate_platform(services=("V001", "V002", "V003"), minutes=1, seed=1)
    cleaned, _ = clean_platform(df)
    platform = platform_summary(cleaned)
    assert platform["services"] == ["V001", "V002", "V003"]
    assert len(platform["rows"]) == 3
    table = platform_table(cleaned)
    assert list(table["service_id"]) == ["V001", "V002", "V003"]


def test_build_dashboard_artifacts() -> None:
    df = generate_platform(services=("V001", "V002", "V003"), minutes=2, seed=9)
    cleaned, _ = clean_platform(df)
    artifacts = build_dashboard(cleaned, _scratch_dir("dashboard"))
    html = Path(artifacts["html"])
    payload = Path(artifacts["json"])
    assert html.exists() and html.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    assert "单实例汇总" in html.read_text(encoding="utf-8")
    data = json.loads(payload.read_text(encoding="utf-8"))
    assert data["services"] == ["V001", "V002", "V003"]
    assert data["total_traffic_gb"] > 0


def test_cli_dashboard_smoke() -> None:
    # 内置样例 + 输出到 /tmp 子目录，走 CLI 真实入口
    out = _scratch_dir("cli")
    cmd_dashboard(platform=None, out=out)
    assert (out / "dashboard.html").exists()
    assert (out / "dashboard.json").exists()
    assert (out / "dashboard.html").stat().st_size > 10_000  # 内嵌图，体积不小


def test_cli_summary_smoke(capsys: pytest.CaptureFixture[str]) -> None:
    cmd_summary(platform=None)
    out = capsys.readouterr().out
    assert "原始" in out and "清洗后" in out
    assert "V001" in out and "单实例汇总" in out


def test_read_platform_rejects_missing_columns() -> None:
    from platdash.data import read_platform

    bad = _scratch_dir("badschema") / "bad.csv"
    pd.DataFrame({"ts": [1.0], "service_id": ["V001"]}).to_csv(bad, index=False)
    with pytest.raises(ValueError, match="缺少列"):
        read_platform(bad)
