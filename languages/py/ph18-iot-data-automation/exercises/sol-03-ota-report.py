#!/usr/bin/env python3
# exercises/sol-03-ota-report.py —— 参考实现：OTA 测试报告生成器（对应 roadmap §18 练习 3）
# 验证环境（目标）：Python 3.13；本机实测 Python 3.13.12，纯标准库
# 运行：python3 sol-03-ota-report.py（生成报告到 /tmp + 断言自检）
# 测试：python3 -m pytest sol-03-ota-report.py -q
# lint：ruff check sol-03-ota-report.py
# 验证状态：已验证（Python 3.13.12 本机实测：运行自检与 pytest 全绿）
"""OTA 测试报告生成：把一次 OTA 推送的逐车结果汇总成可读、可归档的测试报告。

「OTA 测试报告」在车联网里的含义：不是上报 bug 清单，而是对一次软件升级做**版本级
验收** —— 分版本成功率、失败原因分布、耗时统计。产出固定格式的 Markdown，便于进
测试平台（CI 归档/自动比对）。练习要求见 README.md。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

SUCCESS = ("success",)
FAILED = ("failed", "rollback", "timeout")  # 非成功终点


@dataclass(frozen=True, slots=True)
class Attempt:
    """一辆车一次升级尝试（来自 OTA 平台的事件流，简化为一行）。"""

    vehicle_id: str
    ts: float
    from_version: str
    target_version: str
    result: str  # success / failed / rollback / timeout
    reason: str = ""  # 失败原因码，仅非 success 时有意义
    duration_s: float = 0.0


def build_campaign() -> list[Attempt]:
    """一次教学 OTA 演练：3 个目标版本 × 若干车，结果确定（用于精确断言）。"""
    now = 1_700_000_000.0
    rows: list[Attempt] = []
    vehicles = [f"V{i:03d}" for i in range(1, 19)]  # V001..V018
    spec = [
        # (from_version, target_version, success_count, 每条失败(vehicle_offset, result, reason))
        ("1.0.9", "1.1.0", 5, [(5, "failed", "flash_checksum")]),
        ("1.1.0", "1.2.0", 6, [(6, "timeout", "rollback_timeout"), (7, "rollback", "user_cancel")]),
        (
            "1.2.0",
            "1.3.0-beta",
            2,
            [(2, "failed", "compat_mismatch"), (3, "failed", "compat_mismatch")],
        ),
    ]
    offset = 0
    for from_v, target_v, ok_count, fails in spec:
        for i, vid in enumerate(vehicles[offset : offset + ok_count + len(fails)]):
            is_fail = i >= ok_count
            attempt = Attempt(
                vehicle_id=vid,
                ts=now + offset * 100 + i,
                from_version=from_v,
                target_version=target_v,
                result="success" if not is_fail else fails[i - ok_count][1],
                reason="" if not is_fail else fails[i - ok_count][2],
                duration_s=float(120 + i * 7),  # 升级耗时随车递增，便于做耗时统计
            )
            rows.append(attempt)
        offset += ok_count + len(fails)
    return rows


def group_success_rate(attempts: list[Attempt]) -> dict[str, float]:
    """分目标版本算成功率 = success 数 / 该版本总尝试数。"""
    from collections import defaultdict

    total: dict[str, int] = defaultdict(int)
    ok: dict[str, int] = defaultdict(int)
    for a in attempts:
        total[a.target_version] += 1
        ok[a.target_version] += int(a.result == "success")
    return {v: ok[v] / total[v] for v in total}


def failure_reason_counts(attempts: list[Attempt]) -> list[tuple[str, int]]:
    from collections import Counter

    counter = Counter(a.reason for a in attempts if a.reason)
    return counter.most_common()


def build_report(
    attempts: list[Attempt], sort_key: Callable[[Attempt], object] | None = None
) -> str:
    """生成 Markdown 测试报告：总览 → 分版本成功率 → 失败原因 → 耗时统计。"""
    lines: list[str] = [
        "# OTA 升级测试报告",
        "",
        f"- 涉及车辆：{len({a.vehicle_id for a in attempts})} 台",
        f"- 尝试总次数：{len(attempts)}",
    ]
    overall_ok = sum(1 for a in attempts if a.result == "success")
    lines += [
        f"- 总体成功率：{overall_ok / len(attempts):.1%}",
        "",
        "## 分版本成功率",
        "",
        "| 目标版本 | 尝试数 | 成功数 | 成功率 |",
        "|---------|-------|-------|-------|",
    ]
    by_version: dict[str, list[Attempt]] = {}
    for a in attempts:
        by_version.setdefault(a.target_version, []).append(a)
    for version, group in sorted(by_version.items()):
        ok = sum(1 for a in group if a.result == "success")
        lines.append(f"| {version} | {len(group)} | {ok} | {ok / len(group):.1%} |")
    lines += ["", "## 失败原因分布", "", "| 原因码 | 次数 |", "|-------|-----|"]
    for reason, count in failure_reason_counts(attempts):
        lines.append(f"| {reason} | {count} |")
    durations = [a.duration_s for a in attempts if a.duration_s > 0]
    lines += [
        "",
        "## 升级耗时统计",
        "",
        f"- 平均：{sum(durations) / len(durations):.1f}s" if durations else "-",
    ]
    return "\n".join(lines)


def main() -> None:
    attempts = build_campaign()
    report = build_report(attempts)
    out_dir = Path("/tmp/ph18-exer03")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "ota_test_report.md"
    report_path.write_text(report + "\n", encoding="utf-8")
    print(report)

    # ---- 自检 ----
    assert len(attempts) == 18  # 5+1 + 6+2 + 2+2
    assert group_success_rate(attempts) == {
        "1.1.0": 5 / 6,
        "1.2.0": 6 / 8,
        "1.3.0-beta": 0.5,
    }
    assert failure_reason_counts(attempts)[0] == ("compat_mismatch", 2)
    assert "总体成功率：72.2%" in report
    assert report_path.exists() and report_path.stat().st_size > 100
    print(f"\n报告已写：{report_path}")
    print("\n自检通过：成功率分组、失败原因分布、报告文本断言全绿")


def test_build_campaign_shape() -> None:
    attempts = build_campaign()
    assert len(attempts) == 18
    assert all(a.result == "success" for a in attempts if a.reason == "")


def test_success_rate_by_version() -> None:
    attempts = build_campaign()
    rate = group_success_rate(attempts)
    assert rate["1.1.0"] == 5 / 6
    assert rate["1.2.0"] == 6 / 8
    assert rate["1.3.0-beta"] == 2 / 4


def test_report_contains_key_sections() -> None:
    report = build_report(build_campaign())
    for section in ("分版本成功率", "失败原因分布", "升级耗时统计"):
        assert f"## {section}" in report
    assert "| 1.2.0 | 8 | 6 | 75.0% |" in report


if __name__ == "__main__":
    main()
