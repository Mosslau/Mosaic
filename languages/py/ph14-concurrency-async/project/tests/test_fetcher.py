"""fetcher 测试：采集正确性、重试语义、并发一致性（标准 pytest + asyncio.run 包装）。

本文件演示「并发代码怎么测」（主文档 3.9）：每个用例在 asyncio.run 里起模拟
服务器、跑采集、断言，finally 关闭 —— 不需要 pytest-asyncio。
"""

from __future__ import annotations

import asyncio

from collector.fetcher import collect
from collector.simserver import TelemetrySimulator


def test_collect_all_success():
    """fail_rate=0：全部成功、无重试、遥测值完整。"""

    async def _t() -> None:
        sim = TelemetrySimulator(n_vehicles=10, fail_rate=0.0, seed=1)
        await sim.start()
        try:
            results = await collect(sim.base_url, sim.vehicle_ids, max_concurrency=5)
            assert len(results) == 10
            assert all(r.ok for r in results)
            assert all(r.attempts == 1 for r in results)  # 无失败不应重试
            assert all(r.speed is not None for r in results)
            assert all(r.status == 200 for r in results)
        finally:
            await sim.stop()

    asyncio.run(_t())


def test_collect_retry_exhausted():
    """fail_rate=1.0：恒 503，重试耗尽后全部记为失败，attempts == max_retries。"""

    async def _t() -> None:
        sim = TelemetrySimulator(n_vehicles=4, fail_rate=1.0, seed=2)
        await sim.start()
        try:
            results = await collect(sim.base_url, sim.vehicle_ids, max_concurrency=2, max_retries=2)
            assert len(results) == 4
            assert all(not r.ok for r in results)
            assert all(r.attempts == 2 for r in results)
        finally:
            await sim.stop()

    asyncio.run(_t())


def test_collect_mixed_with_retry():
    """fail_rate=0.5：部分成功部分失败，失败项 attempts == max_retries。

    成功数不做精确断言：失败判定与遥测值共用同一 RNG 序列，并发下抽取交错依赖
    请求到达顺序（与调度相关，本机实测 6/4 稳定，但非 API 保证）——区间 2~8
    覆盖 fail_rate=0.5 的绝大多数情形（Bin(10, 0.5) 下 0/1/9/10 之外），
    仍能捕获「全部成功/全部失败」这类重试逻辑损坏。
    """

    async def _t() -> None:
        sim = TelemetrySimulator(n_vehicles=10, fail_rate=0.5, seed=1)
        await sim.start()
        try:
            results = await collect(sim.base_url, sim.vehicle_ids, max_concurrency=3, max_retries=3)
            ok_ids = {r.vehicle_id for r in results if r.ok}
            fail_ids = {r.vehicle_id for r in results if not r.ok}
            assert 2 <= len(ok_ids) <= 8, (
                f"fail_rate=0.5 应成败兼备（本机实测 6/4），实际 {len(ok_ids)}/{len(fail_ids)}"
            )
            for r in results:
                if r.ok:
                    assert r.attempts <= 3
                    assert r.speed is not None
                else:
                    assert r.attempts == 3, "重试耗尽才记为失败"
        finally:
            await sim.stop()

    asyncio.run(_t())


def test_collect_result_consistent_across_concurrency():
    """并发上限不影响结果正确性：max_concurrency=1 与 5 的成功集合一致。"""

    async def _run(concurrency: int) -> set[str]:
        sim = TelemetrySimulator(n_vehicles=12, fail_rate=0.3, seed=99)
        await sim.start()
        try:
            results = await collect(
                sim.base_url, sim.vehicle_ids, max_concurrency=concurrency, max_retries=3
            )
            return {r.vehicle_id for r in results if r.ok}
        finally:
            await sim.stop()

    ok_serial = asyncio.run(_run(1))
    ok_parallel = asyncio.run(_run(5))
    assert ok_serial == ok_parallel
