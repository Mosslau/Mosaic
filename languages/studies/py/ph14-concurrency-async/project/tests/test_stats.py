"""stats 测试：按设备分组汇总与总体统计（纯函数，离线）。"""

from __future__ import annotations

from collector.fetcher import FetchResult
from collector.stats import overall, summarize


def _mk(
    device_id: str,
    ok: bool,
    attempts: int = 1,
    elapsed_ms: float = 10.0,
    speed: float | None = 50.0,
) -> FetchResult:
    return FetchResult(
        device_id=device_id,
        ok=ok,
        status=200 if ok else None,
        attempts=attempts,
        elapsed_ms=elapsed_ms,
        speed=speed,
        component=80.0,
    )


def test_summarize_groups_by_device_sorted():
    results = [
        _mk("EV-002", True),
        _mk("EV-001", True),
        _mk("EV-001", False, attempts=3),
    ]
    summaries = summarize(results)
    assert [s.device_id for s in summaries] == ["EV-001", "EV-002"]  # 按 id 排序
    ev1 = summaries[0]
    assert ev1.attempts == 4  # 两次尝试之和（1 + 3）
    assert ev1.ok is False  # 最后一次尝试失败


def test_summarize_success_takes_last_ok_speed():
    results = [
        _mk("EV-001", True, elapsed_ms=10.0, speed=60.0),
        _mk("EV-001", True, elapsed_ms=20.0, speed=70.0),
    ]
    summaries = summarize(results)
    assert summaries[0].speed == 70.0
    assert summaries[0].elapsed_ms == 30.0


def test_overall_counts():
    results = [_mk(f"EV-{i:03d}", ok=(i % 3 != 0)) for i in range(6)]
    stats = overall(results)
    assert stats.total == 6
    assert stats.success == 4
    assert stats.failed == 2
    assert stats.success_rate_pct == round(4 / 6 * 100, 1)


def test_overall_empty():
    stats = overall([])
    assert stats.total == 0
    assert stats.success == 0
    assert stats.success_rate_pct == 0.0
