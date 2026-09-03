# project/tests/test_vehdash.py —— vehdash 测试套件
# 验证环境：Python 3.13 + pytest 8 + pandas + matplotlib；本机实测 Python 3.13.12
"""8 个用例：清洗计数 / 距离估算 / 过热检测 / SOH 提示 / 报告产物 / CLI 冒烟。"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from vehdash.analyze import fleet_summary, fleet_table, vehicle_summary
from vehdash.clean import clean_fleet
from vehdash.cli import cmd_dashboard, cmd_summary
from vehdash.data import generate_fleet
from vehdash.report import build_dashboard


def _scratch_dir(name: str) -> Path:
    """本测试的产物目录：写 /tmp（受限沙箱里对 pytest tmp_path 的逐层 mkdir 不稳定）。"""
    path = Path("/tmp/ph18-project-tests") / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _vehicle_df(speed: float, seconds: int = 100, vid: str = "V001") -> pd.DataFrame:
    t = pd.Series(range(seconds), dtype=float)
    return pd.DataFrame(
        {
            "ts": t + 1_700_000_000,
            "vehicle_id": vid,
            "speed_kmh": float(speed),
            "soc_pct": 80.0,
            "pack_voltage_v": 380.0,
            "pack_temp_c": 30.0,
            "pack_current_a": -25.0,
            "power_kw": -9.5,
        }
    )


def test_clean_removes_injected_anomalies() -> None:
    df = generate_fleet(vehicles=("V001", "V002", "V003"), minutes=10, seed=5)
    cleaned, stats = clean_fleet(df)
    assert stats.phys_removed["speed_kmh"] == 3  # 每车一个 300 km/h
    assert stats.spike_removed["pack_temp_c"] == 3  # 每车一个 +18℃ 单点尖峰
    assert (cleaned["speed_kmh"] <= 220).all()
    # 三个尖峰都在 ts=200 的那一秒 → 清洗后该时刻无残留行（过热段 57℃ 属持续事件，保留）
    assert cleaned[cleaned["ts"] == 1_700_000_200].empty


def test_vehicle_summary_distance_estimation() -> None:
    # 60 km/h × 100s = 1.6667 km（含首行 dt=1s，尾部缺 dt → 99 段有效积分）
    df = _vehicle_df(speed=60.0, seconds=100)
    summary = vehicle_summary(df)
    assert summary["points"] == 100
    assert abs(summary["distance_km"] - (60 / 3.6 * 99) / 1000.0) < 0.05


def test_hot_seconds_only_on_overheating_vehicle() -> None:
    df = generate_fleet(vehicles=("V001", "V002", "V003"), minutes=10, seed=5)
    cleaned, _ = clean_fleet(df)
    v002 = vehicle_summary(cleaned, "V002")
    v001 = vehicle_summary(cleaned, "V001")
    assert v002["hot_seconds"] >= 6  # 埋了 8s 57℃ 过热
    assert v001["hot_seconds"] == 0


def test_soh_hint_in_plausible_range() -> None:
    summary = vehicle_summary(_vehicle_df(speed=80.0, seconds=600))
    assert 85.0 <= summary["soh_hint_pct"] <= 100.0


def test_fleet_summary_rows_match_vehicles() -> None:
    df = generate_fleet(vehicles=("V001", "V002", "V003"), minutes=1, seed=1)
    cleaned, _ = clean_fleet(df)
    fleet = fleet_summary(cleaned)
    assert fleet["vehicles"] == ["V001", "V002", "V003"]
    assert len(fleet["rows"]) == 3
    table = fleet_table(cleaned)
    assert list(table["vehicle_id"]) == ["V001", "V002", "V003"]


def test_build_dashboard_artifacts() -> None:
    df = generate_fleet(vehicles=("V001", "V002", "V003"), minutes=2, seed=9)
    cleaned, _ = clean_fleet(df)
    artifacts = build_dashboard(cleaned, _scratch_dir("dashboard"))
    html = Path(artifacts["html"])
    payload = Path(artifacts["json"])
    assert html.exists() and html.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    assert "单车汇总" in html.read_text(encoding="utf-8")
    data = json.loads(payload.read_text(encoding="utf-8"))
    assert data["vehicles"] == ["V001", "V002", "V003"]
    assert data["total_distance_km"] > 0


def test_cli_dashboard_smoke() -> None:
    # 内置样例 + 输出到 /tmp 子目录，走 CLI 真实入口
    out = _scratch_dir("cli")
    cmd_dashboard(fleet=None, out=out)
    assert (out / "dashboard.html").exists()
    assert (out / "dashboard.json").exists()
    assert (out / "dashboard.html").stat().st_size > 10_000  # 内嵌图，体积不小


def test_cli_summary_smoke(capsys: pytest.CaptureFixture[str]) -> None:
    cmd_summary(fleet=None)
    out = capsys.readouterr().out
    assert "原始" in out and "清洗后" in out
    assert "V001" in out and "单车汇总" in out


def test_read_fleet_rejects_missing_columns() -> None:
    from vehdash.data import read_fleet

    bad = _scratch_dir("badfleet") / "bad.csv"
    pd.DataFrame({"ts": [1.0], "vehicle_id": ["V001"]}).to_csv(bad, index=False)
    with pytest.raises(ValueError, match="缺少列"):
        read_fleet(bad)
