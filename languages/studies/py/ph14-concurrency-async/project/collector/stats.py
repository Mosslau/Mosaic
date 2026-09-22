"""采集结果汇总：按车辆分组 + 总体统计。"""

from __future__ import annotations

from dataclasses import dataclass

from collector.fetcher import FetchResult


@dataclass
class VehicleSummary:
    """单辆车在本次采集中的汇总。"""

    vehicle_id: str
    ok: bool
    attempts: int
    elapsed_ms: float
    speed: float | None
    battery: float | None


@dataclass
class OverallStats:
    """整批采集的总体统计。"""

    total: int
    success: int
    failed: int
    avg_elapsed_ms: float
    success_rate: float

    @property
    def success_rate_pct(self) -> float:
        return round(self.success_rate * 100, 1)


def summarize(results: list[FetchResult]) -> list[VehicleSummary]:
    """按车辆 id 分组汇总（每辆车一条），按 id 排序保证输出确定性。"""
    by_id: dict[str, list[FetchResult]] = {}
    for r in results:
        by_id.setdefault(r.vehicle_id, []).append(r)

    summaries: list[VehicleSummary] = []
    for vid in sorted(by_id):
        rows = by_id[vid]
        # 取最后一次（成功或失败）的尝试信息
        last = rows[-1]
        ok_rows = [r for r in rows if r.ok]
        summary = VehicleSummary(
            vehicle_id=vid,
            ok=last.ok,
            attempts=sum(r.attempts for r in rows),
            elapsed_ms=round(sum(r.elapsed_ms for r in rows), 1),
            speed=ok_rows[-1].speed if ok_rows else None,
            battery=ok_rows[-1].battery if ok_rows else None,
        )
        summaries.append(summary)
    return summaries


def overall(results: list[FetchResult]) -> OverallStats:
    """总体统计：总数 / 成功 / 失败 / 平均耗时 / 成功率。"""
    total = len(results)
    success = sum(1 for r in results if r.ok)
    failed = total - success
    ok_elapsed = [r.elapsed_ms for r in results if r.ok]
    avg = sum(ok_elapsed) / len(ok_elapsed) if ok_elapsed else 0.0
    return OverallStats(
        total=total,
        success=success,
        failed=failed,
        avg_elapsed_ms=round(avg, 1),
        success_rate=success / total if total else 0.0,
    )
