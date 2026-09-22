#!/usr/bin/env python3
# examples/ex04-fault-report.py —— 故障诊断规则引擎 + 报表生成（主文档 3.4）
# 验证环境：Python 3.13 + pandas + matplotlib；本机实测 3.13.12 + pandas 3.0.5 + matplotlib 3.11.1
# 运行：python3 ex04-fault-report.py（打印教学输出 + 断言自检，失败退出码非 0）
# 测试：python3 -m pytest ex04-fault-report.py -q（收集 test_* 跑断言）
# lint：ruff check ex04-fault-report.py
# 验证状态：已验证（Python 3.13.12 + pandas 3.0.5 + matplotlib 3.11.1 本机实测：自检与 pytest 全绿）
"""故障诊断：把「规则」声明成数据（dataclass），在遥测上扫描并生成可读报表。

车辆故障诊断的两条腿：一条是 DTC（诊断故障码，OBD 时代由 ECU 自报），一条是**数据侧
规则引擎**——云端拿不到 ECU 内部码时，靠信号模式的持续异常推断。本示例演示后者，并
把命中结果导出为 Markdown 报表 + Matplotlib 统计图（ph09/ph12 的报表技能落地）。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无显示环境（服务器/CI）也能出图
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


def _setup_cjk_font() -> None:
    """中文字体回退链（macOS PingFang/Hiragino → Linux Noto → Windows 微软雅黑）。"""
    from matplotlib import font_manager, rcParams

    candidates = (
        "PingFang SC",
        "Hiragino Sans GB",
        "Noto Sans CJK SC",
        "Microsoft YaHei",
        "WenQuanYi Micro Hei",
    )
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in installed:
            rcParams["font.sans-serif"] = [name, "DejaVu Sans"]
            rcParams["axes.unicode_minus"] = False
            return


@dataclass(frozen=True, slots=True)
class FaultRule:
    """一条诊断规则：名字、级别、触发谓词与描述模板（谓词输入为该车的全量帧）。"""

    name: str
    severity: str  # high / medium / low
    dtc: str  # 诊断故障码（映射到行业惯例的 UDS/OBD 码，教学示意）
    description: str
    check: Callable[[pd.DataFrame], pd.Series]  # 返回布尔 Series（True = 命中）
    window: int = 0  # 用于信息展示

    def __post_init__(self) -> None:
        if not callable(self.check):
            raise TypeError("check 必须是一个接收 DataFrame 返回布尔 Series 的函数")


# ---- 规则库（可扩展：新增规则 = 新增一个 dataclass 实例，引擎不用改）----


def _rule_temp_high(telemetry: pd.DataFrame) -> pd.Series:
    rolling = telemetry["pack_temp_c"].rolling(10, center=True, min_periods=5).mean()
    return rolling > 55.0


def _rule_soc_fast_drop(telemetry: pd.DataFrame) -> pd.Series:
    delta = telemetry["soc_pct"].diff(60)  # 与 60s 前比
    return delta < -15.0


def _rule_current_limit(telemetry: pd.DataFrame) -> pd.Series:
    return telemetry["pack_current_a"].rolling(10, center=True, min_periods=5).mean() < -200.0


def _rule_sensor_stuck(telemetry: pd.DataFrame) -> pd.Series:
    """速度信号连续 30s 方差不大于 0.01，但功率仍有明显输出 → 传感器疑似卡死。"""
    speed_std = telemetry["speed_kmh"].rolling(30, center=True, min_periods=30).std()
    power_abs_mean = telemetry["power_kw"].abs().rolling(30, center=True, min_periods=30).mean()
    return (speed_std < 0.01) & (power_abs_mean > 8.0)  # 两条 Series 逐元素与，不能写 and


FAULT_RULES: tuple[FaultRule, ...] = (
    FaultRule("overheating", "high", "P0A80", "电池包持续高温（>55℃ 滚动均值）", _rule_temp_high),
    FaultRule("soc_cliff", "high", "P0AC4", "SOC 60s 内骤降 >15%", _rule_soc_fast_drop),
    FaultRule(
        "current_limit", "high", "P0C00", "持续过放电流（10s 均值 <-200A）", _rule_current_limit
    ),
    FaultRule(
        "sensor_stuck",
        "low",
        "U0100",
        "车速传感器疑似卡死（功率大但速度恒为 0）",
        _rule_sensor_stuck,
    ),
)


@dataclass(frozen=True, slots=True)
class FaultEvent:
    """一次命中的故障：规则 + 起始/结束时刻 + 命中统计值摘要。"""

    vehicle_id: str
    rule: str
    dtc: str
    severity: str
    ts_start: float
    ts_end: float
    detail: str


def detect_faults(
    telemetry: pd.DataFrame, rules: tuple[FaultRule, ...] = FAULT_RULES
) -> list[FaultEvent]:
    """按车应用全部规则；连续命中合并为一条事件（runs 语义）。"""
    events: list[FaultEvent] = []
    for _vid, grp in telemetry.groupby("vehicle_id", sort=False):
        grp = grp.sort_values("ts").reset_index(drop=True)
        for rule in rules:
            hit = rule.check(grp).fillna(False).astype(bool)
            start: int | None = None
            for i, is_hit in enumerate(hit.tolist()):
                if is_hit and start is None:
                    start = i
                elif not is_hit and start is not None:
                    events.append(_mk_event(grp, rule, start, i - 1))
                    start = None
            if start is not None:
                events.append(_mk_event(grp, rule, start, len(hit) - 1))
    return sorted(events, key=lambda e: (e.vehicle_id, e.ts_start))


def _mk_event(grp: pd.DataFrame, rule: FaultRule, start: int, end: int) -> FaultEvent:
    ts0, ts1 = grp["ts"].iloc[start], grp["ts"].iloc[end]
    # detail：展示该窗口内的关键量级（对数值型信号取中位数，给报表一个"多严重"的抓手）
    numeric = grp.select_dtypes(include=[np.number]).drop(columns=["ts"])
    peaks = {col: float(numeric[col].iloc[start : end + 1].median()) for col in numeric.columns}
    return FaultEvent(
        vehicle_id=str(grp["vehicle_id"].iloc[0]),
        rule=rule.name,
        dtc=rule.dtc,
        severity=rule.severity,
        ts_start=ts0,
        ts_end=ts1,
        detail=f"{rule.description}（窗口 {int(ts1 - ts0) + 1}s，量级峰值 {peaks}）",
    )


def generate_fleet_telemetry(seed: int = 5) -> pd.DataFrame:
    """自造 3 车 × 1200s 遥测；V002 注入持续过热段、V003 注入 SOC 骤降 + 卡死车速。"""
    rng = np.random.default_rng(seed)
    t = np.arange(1200, dtype=float)
    rows: list[pd.DataFrame] = []
    for vehicle_id in ("V001", "V002", "V003"):
        temp = 30 + rng.normal(0, 0.5, 1200)
        if vehicle_id == "V002":  # t 600~760 过热到 58~62℃
            temp[600:761] = np.linspace(35, 60, 161) + rng.normal(0, 0.4, 161)
        speed = 40 + 30 * np.sin(t / 90.0) + rng.normal(0, 0.6, 1200)
        if vehicle_id == "V003":  # t 800~1000 传感器卡死：速度冻结但功率仍在
            speed[800:1001] = 0.0
        soc = 85 - t / 90.0 + rng.normal(0, 0.08, 1200)
        if vehicle_id == "V003":  # t 550 处 60s 内掉 25%
            soc[550:611] = np.linspace(soc[549], soc[550] - 25.0, 61)
        current = -25 - speed / 12.0 + rng.normal(0, 1.2, 1200)
        voltage = 385 + rng.normal(0, 0.5, 1200)
        power = voltage * current / 1000.0
        df = pd.DataFrame(
            {
                "ts": t + 1_700_000_000,
                "vehicle_id": vehicle_id,
                "speed_kmh": speed,
                "soc_pct": soc,
                "pack_voltage_v": voltage,
                "pack_temp_c": temp,
                "pack_current_a": current,
                "power_kw": power,
            }
        )
        rows.append(df)
    return pd.concat(rows, ignore_index=True)


def build_report(
    events: list[FaultEvent], telemetry: pd.DataFrame, out_dir: Path
) -> tuple[Path, Path]:
    """生成 Markdown 报表 + 规则命中分布柱状图，返回 (md 路径, png 路径)。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "fault_report.md"
    png_path = out_dir / "fault_distribution.png"
    _setup_cjk_font()  # 图含中文标签/标题，先备好字体

    # ---- 文本报表 ----
    md: list[str] = [
        "# 车队故障诊断报表",
        "",
        f"- 数据窗口：ts ∈ [{telemetry['ts'].min():.0f}, {telemetry['ts'].max():.0f}]",
        f"- 车辆数：{telemetry['vehicle_id'].nunique()}",
        f"- 故障事件总数：{len(events)}",
        "",
        "## 按级别汇总",
        "",
    ]
    severity_counts = pd.Series([e.severity for e in events]).value_counts()
    for sev, count in severity_counts.items():
        md.append(f"- {sev}：{count}")
    md += [
        "",
        "## 事件明细",
        "",
        "| 车辆 | 时间(起始) | 规则 | DTC | 级别 | 窗口 |",
        "|------|-----------|------|-----|------|------|",
    ]
    for ev in events[:50]:
        ts = pd.to_datetime(ev.ts_start, unit="s").isoformat(timespec="seconds")
        md.append(
            f"| {ev.vehicle_id} | {ts} | {ev.rule} | {ev.dtc} | {ev.severity} | {ev.detail} |"
        )
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    # ---- 统计图（ph09 的 matplotlib 技能：服务结论）----
    counts = pd.Series([(e.rule, e.severity) for e in events]).value_counts().sort_index()
    if not counts.empty:
        rules = [f"{r}\n({s})" for (r, s) in counts.index]
        colors = {"high": "#c0392b", "medium": "#e67e22", "low": "#2980b9"}
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(rules, counts.values, color=[colors[s] for _, s in counts.index])
        ax.set_title("故障事件分布（按规则 × 级别）")
        ax.set_ylabel("事件数")
        fig.tight_layout()
        fig.savefig(png_path, dpi=110)
        plt.close(fig)
    return md_path, png_path


def main() -> None:
    telemetry = generate_fleet_telemetry()
    events = detect_faults(telemetry)
    print("== 检出故障事件 ==")
    for ev in events:
        print(
            f"  {ev.vehicle_id} @ts={ev.ts_start:.0f} "
            f"[{ev.severity}] {ev.dtc} {ev.rule}: {ev.detail}"
        )
    md_path, png_path = build_report(events, telemetry, Path("/tmp/ph18-ex04"))
    print(f"\n报表：{md_path}\n图表：{png_path}")

    # ---- 自检断言：注入的故障全部命中且车次正确 ----
    v002_heat = [e for e in events if e.vehicle_id == "V002" and e.rule == "overheating"]
    v003_cliff = [e for e in events if e.vehicle_id == "V003" and e.rule == "soc_cliff"]
    v003_stuck = [e for e in events if e.vehicle_id == "V003" and e.rule == "sensor_stuck"]
    assert v002_heat, "V002 过热段必须被检出"
    assert v003_cliff, "V003 SOC 骤降必须被检出"
    assert v003_stuck, "V003 传感器卡死必须被检出"
    assert not [e for e in events if e.vehicle_id == "V001"], "健康车 V001 不应命中任何规则"
    assert all(e.severity in {"high", "medium", "low"} for e in events)
    assert md_path.exists() and png_path.exists() and md_path.stat().st_size > 0
    print("\n自检通过：注入故障全命中、健康车零误报、报表产物已生成")


def test_no_fault_on_healthy_vehicle() -> None:
    # 单车上 100s 平稳数据：不应命中任何规则（滚动窗口过短的边界段除外，用长窗口规避）
    rng = np.random.default_rng(0)
    t = np.arange(1000, dtype=float)
    df = pd.DataFrame(
        {
            "ts": t + 1_700_000_000,
            "vehicle_id": "V001",
            "speed_kmh": 50 + rng.normal(0, 0.5, 1000),
            "soc_pct": np.linspace(90, 70, 1000),
            "pack_voltage_v": 385 + rng.normal(0, 0.4, 1000),
            "pack_temp_c": 30 + rng.normal(0, 0.4, 1000),
            "pack_current_a": -30 + rng.normal(0, 1.0, 1000),
            "power_kw": 385 * (-30) / 1000 + rng.normal(0, 0.5, 1000),
        }
    )
    assert detect_faults(df) == []


def test_single_overheat_window_yields_one_event() -> None:
    rng = np.random.default_rng(1)
    t = np.arange(200, dtype=float)
    temp = 30 + rng.normal(0, 0.3, 200)
    temp[100:140] = 62.0  # 持续 40s 高温
    df = pd.DataFrame(
        {
            "ts": t + 1_700_000_000,
            "vehicle_id": "V002",
            "speed_kmh": 40 + rng.normal(0, 0.5, 200),
            "soc_pct": np.linspace(80, 75, 200),
            "pack_voltage_v": 385 + rng.normal(0, 0.4, 200),
            "pack_temp_c": temp,
            "pack_current_a": -25 + rng.normal(0, 1.0, 200),
            "power_kw": -9.6 + rng.normal(0, 0.4, 200),
        }
    )
    events = detect_faults(df)
    heat = [e for e in events if e.rule == "overheating"]
    assert len(heat) == 1
    assert heat[0].ts_end - heat[0].ts_start >= 30  # 事件窗口≈持续时长


if __name__ == "__main__":
    main()
