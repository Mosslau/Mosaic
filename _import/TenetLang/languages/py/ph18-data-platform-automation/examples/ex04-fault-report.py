#!/usr/bin/env python3
# examples/ex04-fault-report.py —— 故障故障定位规则引擎 + 报表生成（主文档 3.4）
# 验证环境：Python 3.13 + pandas + matplotlib；本机实测 3.13.12 + pandas 3.0.5 + matplotlib 3.11.1
# 运行：python3 ex04-fault-report.py（打印教学输出 + 断言自检，失败退出码非 0）
# 测试：python3 -m pytest ex04-fault-report.py -q（收集 test_* 跑断言）
# lint：ruff check ex04-fault-report.py
# 验证状态：已验证（Python 3.13.12 + pandas 3.0.5 + matplotlib 3.11.1 本机实测：自检与 pytest 全绿）
"""故障故障定位：把「规则」声明成数据（dataclass），在指标上扫描并生成可读报表。

平台故障定位的两条腿：一条是告警码（ALERT_CODE，由服务/节点自报），一条是**数据侧
规则引擎**——云端拿不到 ECU 内部码时，靠字段模式的持续异常推断。本示例演示后者，并
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
    """一条故障定位规则：名字、级别、触发谓词与描述模板（谓词输入为该服务实例的全量记录）。"""

    name: str
    severity: str  # high / medium / low
    alert_code: str  # 故障定位告警码（映射到平台告警码习惯，教学示意）
    description: str
    check: Callable[[pd.DataFrame], pd.Series]  # 返回布尔 Series（True = 命中）
    window: int = 0  # 用于信息展示

    def __post_init__(self) -> None:
        if not callable(self.check):
            raise TypeError("check 必须是一个接收 DataFrame 返回布尔 Series 的函数")


# ---- 规则库（可扩展：新增规则 = 新增一个 dataclass 实例，引擎不用改）----


def _rule_temp_high(metrics: pd.DataFrame) -> pd.Series:
    rolling = metrics["disk_temp_c"].rolling(10, center=True, min_periods=5).mean()
    return rolling > 75.0


def _rule_usage_fast_drop(metrics: pd.DataFrame) -> pd.Series:
    delta = metrics["cpu_pct"].diff(60)  # 与 60s 前比
    return delta < -15.0


def _rule_traffic_stall(metrics: pd.DataFrame) -> pd.Series:
    return metrics["net_io_mb_s"].rolling(10, center=True, min_periods=5).mean() < 80.0


def _rule_sensor_stuck(metrics: pd.DataFrame) -> pd.Series:
    """延迟字段连续 30s 方差不大于 0.01，但功耗仍有明显输出 → 指标疑似冻结。"""
    speed_std = metrics["latency_ms"].rolling(30, center=True, min_periods=30).std()
    power_abs_mean = metrics["power_w"].abs().rolling(30, center=True, min_periods=30).mean()
    return (speed_std < 0.01) & (power_abs_mean > 100.0)  # 两条 Series 逐元素与，不能写 and


FAULT_RULES: tuple[FaultRule, ...] = (
    FaultRule("overheat", "high", "P0A80", "节点磁盘持续高温（>75℃ 滚动均值）", _rule_temp_high),
    FaultRule("usage_cliff", "high", "P0AC4", "CPU 60s 内骤降 >15%", _rule_usage_fast_drop),
    FaultRule(
        "traffic_stall", "high", "P0C00", "网络吞吐塌陷（10s 均值 <80MB/s）", _rule_traffic_stall
    ),
    FaultRule(
        "sensor_stuck",
        "low",
        "U0100",
        "延迟指标疑似冻结（功耗正常但延迟方差为 0）",
        _rule_sensor_stuck,
    ),
)


@dataclass(frozen=True, slots=True)
class FaultEvent:
    """一次命中的故障：规则 + 起始/结束时刻 + 命中统计值摘要。"""

    service_id: str
    rule: str
    alert_code: str
    severity: str
    ts_start: float
    ts_end: float
    detail: str


def detect_faults(
    metrics: pd.DataFrame, rules: tuple[FaultRule, ...] = FAULT_RULES
) -> list[FaultEvent]:
    """按服务实例应用全部规则；连续命中合并为一条事件（runs 语义）。"""
    events: list[FaultEvent] = []
    for _vid, grp in metrics.groupby("service_id", sort=False):
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
    return sorted(events, key=lambda e: (e.service_id, e.ts_start))


def _mk_event(grp: pd.DataFrame, rule: FaultRule, start: int, end: int) -> FaultEvent:
    ts0, ts1 = grp["ts"].iloc[start], grp["ts"].iloc[end]
    # detail：展示该窗口内的关键量级（对数值型字段取中位数，给报表一个"多严重"的抓手）
    numeric = grp.select_dtypes(include=[np.number]).drop(columns=["ts"])
    peaks = {col: float(numeric[col].iloc[start : end + 1].median()) for col in numeric.columns}
    return FaultEvent(
        service_id=str(grp["service_id"].iloc[0]),
        rule=rule.name,
        alert_code=rule.alert_code,
        severity=rule.severity,
        ts_start=ts0,
        ts_end=ts1,
        detail=f"{rule.description}（窗口 {int(ts1 - ts0) + 1}s，量级峰值 {peaks}）",
    )


def generate_platform_metrics(seed: int = 5) -> pd.DataFrame:
    """自造 3 个服务实例 × 1200s 指标：V002 注入过热 + 吞吐塌陷，V003 注入 CPU 骤降 + 冻结。"""
    rng = np.random.default_rng(seed)
    t = np.arange(1200, dtype=float)
    rows: list[pd.DataFrame] = []
    for service_id in ("V001", "V002", "V003"):
        temp = 38 + rng.normal(0, 0.5, 1200)
        if service_id == "V002":  # t 600~760 过热到 78~84℃
            temp[600:761] = np.linspace(55, 82, 161) + rng.normal(0, 0.4, 161)
        latency = 55 + 30 * np.sin(t / 90.0) + rng.normal(0, 0.6, 1200)
        if service_id == "V003":  # t 800~1000 延迟指标冻结：方差为 0 但功耗照常
            latency[800:1001] = 55.0
        cpu = 85 - t / 90.0 + rng.normal(0, 0.08, 1200)
        if service_id == "V003":  # t 550 处 60s 内掉 25%
            cpu[550:611] = np.linspace(cpu[549], cpu[550] - 25.0, 61)
        net_io = 320 + latency * 1.5 + rng.normal(0, 1.2, 1200)
        if service_id == "V002":  # t 900~1010 吞吐塌陷（10s 均值 <80MB/s）
            net_io[900:1011] = 10.0 + rng.normal(0, 0.5, 111)
        mem = 96 + rng.normal(0, 0.5, 1200)
        power = 180 + cpu * 2.4 + net_io * 0.08
        df = pd.DataFrame(
            {
                "ts": t + 1_700_000_000,
                "service_id": service_id,
                "latency_ms": latency,
                "cpu_pct": cpu,
                "mem_used_gb": mem,
                "disk_temp_c": temp,
                "net_io_mb_s": net_io,
                "power_w": power,
            }
        )
        rows.append(df)
    return pd.concat(rows, ignore_index=True)


def build_report(
    events: list[FaultEvent], metrics: pd.DataFrame, out_dir: Path
) -> tuple[Path, Path]:
    """生成 Markdown 报表 + 规则命中分布柱状图，返回 (md 路径, png 路径)。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "fault_report.md"
    png_path = out_dir / "fault_distribution.png"
    _setup_cjk_font()  # 图含中文标签/标题，先备好字体

    # ---- 文本报表 ----
    md: list[str] = [
        "# 平台故障故障定位报表",
        "",
        f"- 数据窗口：ts ∈ [{metrics['ts'].min():.0f}, {metrics['ts'].max():.0f}]",
        f"- 服务实例数：{metrics['service_id'].nunique()}",
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
        "| 服务实例 | 时间(起始) | 规则 | ALERT_CODE | 级别 | 窗口 |",
        "|------|-----------|------|-----|------|------|",
    ]
    for ev in events[:50]:
        ts = pd.to_datetime(ev.ts_start, unit="s").isoformat(timespec="seconds")
        md.append(
            f"| {ev.service_id} | {ts} | {ev.rule} | {ev.alert_code} "
            f"| {ev.severity} | {ev.detail} |"
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
    metrics = generate_platform_metrics()
    events = detect_faults(metrics)
    print("== 检出故障事件 ==")
    for ev in events:
        print(
            f"  {ev.service_id} @ts={ev.ts_start:.0f} "
            f"[{ev.severity}] {ev.alert_code} {ev.rule}: {ev.detail}"
        )
    md_path, png_path = build_report(events, metrics, Path("/tmp/ph18-ex04"))
    print(f"\n报表：{md_path}\n图表：{png_path}")

    # ---- 自检断言：注入的故障全部命中且服务实例正确 ----
    v002_heat = [e for e in events if e.service_id == "V002" and e.rule == "overheat"]
    v003_cliff = [e for e in events if e.service_id == "V003" and e.rule == "usage_cliff"]
    v002_stall = [e for e in events if e.service_id == "V002" and e.rule == "traffic_stall"]
    v003_stuck = [e for e in events if e.service_id == "V003" and e.rule == "sensor_stuck"]
    assert v002_heat, "V002 过热段必须被检出"
    assert v002_stall, "V002 吞吐塌陷必须被检出"
    assert v003_cliff, "V003 CPU 骤降必须被检出"
    assert v003_stuck, "V003 传感器卡死必须被检出"
    assert not [e for e in events if e.service_id == "V001"], "健康服务实例 V001 不应命中任何规则"
    assert all(e.severity in {"high", "medium", "low"} for e in events)
    assert md_path.exists() and png_path.exists() and md_path.stat().st_size > 0
    print("\n自检通过：注入故障全命中、健康服务实例零误报、报表产物已生成")


def test_no_fault_on_healthy_service() -> None:
    # 单个服务实例上 100s 平稳数据：不应命中任何规则（滚动窗口过短的边界段除外，用长窗口规避）
    rng = np.random.default_rng(0)
    t = np.arange(1000, dtype=float)
    df = pd.DataFrame(
        {
            "ts": t + 1_700_000_000,
            "service_id": "V001",
            "latency_ms": 50 + rng.normal(0, 0.5, 1000),
            "cpu_pct": np.linspace(90, 70, 1000),
            "mem_used_gb": 96 + rng.normal(0, 0.4, 1000),
            "disk_temp_c": 38 + rng.normal(0, 0.4, 1000),
            "net_io_mb_s": 320 + rng.normal(0, 1.0, 1000),
            "power_w": 340 + rng.normal(0, 0.5, 1000),
        }
    )
    assert detect_faults(df) == []


def test_single_overheat_window_yields_one_event() -> None:
    rng = np.random.default_rng(1)
    t = np.arange(200, dtype=float)
    temp = 38 + rng.normal(0, 0.3, 200)
    temp[100:140] = 82.0  # 持续 40s 高温
    df = pd.DataFrame(
        {
            "ts": t + 1_700_000_000,
            "service_id": "V002",
            "latency_ms": 40 + rng.normal(0, 0.5, 200),
            "cpu_pct": np.linspace(80, 75, 200),
            "mem_used_gb": 96 + rng.normal(0, 0.4, 200),
            "disk_temp_c": temp,
            "net_io_mb_s": 320 + rng.normal(0, 1.0, 200),
            "power_w": 340 + rng.normal(0, 0.4, 200),
        }
    )
    events = detect_faults(df)
    heat = [e for e in events if e.rule == "overheat"]
    assert len(heat) == 1
    assert heat[0].ts_end - heat[0].ts_start >= 30  # 事件窗口≈持续时长


if __name__ == "__main__":
    main()
