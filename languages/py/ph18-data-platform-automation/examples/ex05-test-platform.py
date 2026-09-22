#!/usr/bin/env python3
# examples/ex05-test-platform.py —— 自动化测试平台：pytest 基础设施（主文档 3.5）
# 验证环境：Python 3.13 + pytest + ruff；本机实测 3.13.12 + pytest 9.1.1 + ruff 0.16.5
# 运行：python3 ex05-test-platform.py（打印教学输出 + 断言自检）
# 测试：python3 -m pytest ex05-test-platform.py -q（收集本文件 test_* 跑断言）
# 按标记跑子集：python3 -m pytest ex05-test-platform.py -m platform -q
# lint：ruff check ex05-test-platform.py
# 验证状态：已验证（Python 3.13.12 + pytest 9.1.1 本机实测：自检与 pytest 全绿）
"""自动化测试平台示例：把 ph13 的 pytest 方法论固化成「可复用的数据质量门禁」。

真实的"测试平台"长这样：一批**面向数据的检查函数**（列完整性/采样率/量程）+ 一套
pytest 脚手架（fixture 造样本、parametrize 铺场景、marker 分套件、golden 报告快照）。
平台的价值 = 可重复 + 可审计（roadmap 必会概念）：同一套检查在开发机与 CI 上跑出
完全一样的结果，任何清洗/解析改动都能先被回归拦下来。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# 列完整性门禁：缺列的批数据直接判不通过
REQUIRED_COLUMNS = (
    "ts",
    "service_id",
    "latency_ms",
    "cpu_pct",
    "mem_used_gb",
    "disk_temp_c",
    "net_io_mb_s",
    "power_w",
)

# 量程门禁：与 ex02 的 PHYSICAL_RANGES 一致（平台与清洗共用同一份规格）
RANGE_SPEC: dict[str, tuple[float, float]] = {
    "latency_ms": (0.0, 220.0),
    "cpu_pct": (0.0, 100.0),
    "mem_used_gb": (250.0, 420.0),
    "disk_temp_c": (-40.0, 65.0),
    "net_io_mb_s": (-300.0, 400.0),
    "power_w": (-300.0, 300.0),
}


@dataclass
class GateResult:
    """一次数据门禁的执行结果：通过/失败 + 可读报告行。"""

    name: str
    passed: bool
    detail: str

    def line(self) -> str:
        mark = "PASS" if self.passed else "FAIL"
        return f"[{mark}] {self.name}: {self.detail}"


class MissingColumnError(ValueError):
    """平台自抛的缺列异常：把「数据规格不符」与业务 ValueError 区分开。"""


# ---- 平台核心：三个检查函数（业务方注册即可，无需改平台代码）----


def check_columns(df: pd.DataFrame) -> GateResult:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise MissingColumnError(f"缺少列 {missing}")  # 结构性失败：直接抛而非返 FAIL
    return GateResult("columns", True, f"{len(REQUIRED_COLUMNS)} 列齐全")


def check_sampling(df: pd.DataFrame, max_gap_s: float = 5.0) -> GateResult:
    """按服务实例检查时间连续性：>1.2s 的间隙视为掉点，最大允许 max_gap_s。"""
    worst_gap = 0.0
    total_gaps = 0
    for _vid, grp in df.groupby("service_id"):
        ts = grp.sort_values("ts")["ts"].to_numpy()
        gaps = np.diff(ts)
        total_gaps += int((gaps > 1.2).sum())
        worst_gap = max(worst_gap, float(gaps.max()) if gaps.size else 0.0)
    return GateResult(
        "sampling",
        worst_gap <= max_gap_s,
        f"掉点 {total_gaps} 处，最大间隙 {worst_gap:.1f}s（阈值 {max_gap_s}s）",
    )


def check_ranges(df: pd.DataFrame) -> GateResult:
    bad: list[str] = []
    for col, (lo, hi) in RANGE_SPEC.items():
        if col not in df.columns:  # 缺列归 columns 门禁管，这里跳过避免 KeyError
            continue
        n_out = int((~df[col].between(lo, hi)).sum())
        if n_out:
            bad.append(f"{col}×{n_out}")
    return GateResult("ranges", not bad, "越界: " + ", ".join(bad) if bad else "全部在量程内")


ALL_GATES: list[Callable[[pd.DataFrame], GateResult]] = [
    check_columns,
    check_sampling,
    check_ranges,
]


def run_gates(df: pd.DataFrame) -> list[GateResult]:
    """平台执行入口：跑全部门禁，异常（缺列）转为 FAIL 结果而不是中断整批。"""
    results: list[GateResult] = []
    for gate in ALL_GATES:
        try:
            results.append(gate(df))
        except MissingColumnError as exc:
            results.append(GateResult("columns", False, str(exc)))
    return results


# ---- 样本生成：供平台演示与测试的确定性数据（与 pytest fixture 共用）----


def build_scenario(
    service_id: str = "V001",
    seconds: int = 300,
    seed: int = 0,
    *,
    drop_cols: tuple[str, ...] = (),
    tamper: dict[str, float] | None = None,
    hole: tuple[int, int] | None = None,
) -> pd.DataFrame:
    """按参数构造批数据场景；测试用不同参数组合出"好/坏"数据。"""
    rng = np.random.default_rng(seed)
    t = np.arange(seconds, dtype=float)
    df = pd.DataFrame(
        {
            "ts": t + 1_700_000_000,
            "service_id": service_id,
            "latency_ms": 50 + 10 * np.sin(t / 40.0) + rng.normal(0, 0.3, seconds),
            "cpu_pct": np.clip(85 - t * 0.02 + rng.normal(0, 0.05, seconds), 0, 100),
            "mem_used_gb": 385 + rng.normal(0, 0.4, seconds),
            "disk_temp_c": 32 + rng.normal(0, 0.3, seconds),
            "net_io_mb_s": -28 + rng.normal(0, 1.0, seconds),
            "power_w": -10.8 + rng.normal(0, 0.5, seconds),
        }
    )
    if hole is not None:
        start, end = hole
        df = df[~df["ts"].between(1_700_000_000 + start, 1_700_000_000 + end)].copy()
    if tamper:
        for col, value in tamper.items():
            df.loc[5, col] = value  # 在第 5 行注入越界/异常值
    for col in drop_cols:
        df = df.drop(columns=[col])
    return df


def main() -> None:
    print("== 平台演示：对一批合格数据跑门禁 ==")
    good = build_scenario("V001", seconds=300, seed=0)
    for res in run_gates(good):
        print("  " + res.line())
    assert all(r.passed for r in run_gates(good))

    print("\n== 对三批带病数据跑门禁 ==")
    cases = {
        "缺 cpu_pct 列": build_scenario(drop_cols=("cpu_pct",)),
        "电压越界 500V": build_scenario(tamper={"mem_used_gb": 500.0}),
        "10s 连续掉点": build_scenario(hole=(100, 110)),
    }
    for name, df in cases.items():
        verdict = "ALL PASS" if all(r.passed for r in run_gates(df)) else "HAS FAIL"
        print(f"  {name} → {verdict}")
    assert any(not r.passed for r in run_gates(cases["缺 cpu_pct 列"]))
    assert any(not r.passed for r in run_gates(cases["电压越界 500V"]))
    assert any(not r.passed for r in run_gates(cases["10s 连续掉点"]))

    # 门禁结果可序列化 → 测试平台天然可审计（每次 CI 结果落盘比对）
    report_md = Path("/tmp/ph18-ex05") / "gate_report.md"
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text("\n".join(res.line() for res in run_gates(good)) + "\n", encoding="utf-8")
    print(f"\n门禁报告已写：{report_md}")
    print("\n自检通过：合格批次全 PASS、三种带病数据均被拦下")


# ---- pytest 基础设施演示（fixture / parametrize / marker / tmp_path）----


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "platform: 平台回归套件（roadmap 自动化测试平台）")


def _scratch(name: str) -> Path:
    path = Path("/tmp/ph18-ex05-tests") / name
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def platform_csv() -> Path:
    """fixture：造一批"好数据"CSV 到 /tmp 子目录并返回路径（平台数据工件）。"""
    good = build_scenario("V001", seconds=120, seed=42)
    path = _scratch("fixtures") / "platform_good.csv"
    good.to_csv(path, index=False)
    return path


def test_gates_pass_on_fixture(platform_csv: Path) -> None:
    """用 fixture 提供的 CSV 回归：读入即过全部门禁。"""
    df = pd.read_csv(platform_csv)
    assert all(gate.passed for gate in run_gates(df))


@pytest.mark.parametrize(
    ("kwargs", "expect_fail_gate"),
    [
        ({"drop_cols": ("power_w",)}, "columns"),
        ({"tamper": {"cpu_pct": -5.0}}, "ranges"),
        ({"hole": (200, 250)}, "sampling"),
    ],
)
def test_bad_batches_fail_expected_gate(kwargs: dict, expect_fail_gate: str) -> None:
    """parametrize 铺场景：坏数据必须被「对应的」那扇门拦下（回归护栏）。"""
    df = build_scenario(**kwargs, seconds=300)
    by_name = {r.name: r for r in run_gates(df)}
    assert by_name[expect_fail_gate].passed is False
    for name, res in by_name.items():
        if name != expect_fail_gate:
            assert res.passed, f"门禁 {name} 不应误拦 {kwargs}"


@pytest.mark.platform
def test_golden_report_snapshot() -> None:
    """golden 文件测试：平台报告固定写到文件并断言关键行（防输出漂移）。"""
    good = build_scenario("V001", seconds=60, seed=1)
    path = _scratch("golden") / "snapshot.md"
    path.write_text("\n".join(res.line() for res in run_gates(good)), encoding="utf-8")
    content = path.read_text(encoding="utf-8")
    assert "[PASS] columns: 8 列齐全" in content
    assert "[PASS] ranges:" in content  # 正常批次 ranges 行以 [PASS] 开头
    assert "FAIL" not in content


def test_missing_column_raises_typed_error() -> None:
    """结构性缺列应抛专用异常（平台按此区分"修数据"还是"修代码"）。"""
    df = build_scenario(drop_cols=("ts",))
    with pytest.raises(MissingColumnError):
        check_columns(df)


if __name__ == "__main__":
    main()
