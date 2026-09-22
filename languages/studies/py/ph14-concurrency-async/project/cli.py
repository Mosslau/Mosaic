#!/usr/bin/env python3
"""异步遥测采集服务的命令行入口。

流程：起模拟遥测服务器 → aiohttp 并发采集（限速 + 重试）→ 汇总统计 → CSV 报表。
用法：
    python3 cli.py --demo                 # 离线自检（短参数、断言全过）
    python3 cli.py                        # 默认跑一次采集（20 辆车，10% 失败率）
    python3 cli.py --vehicles 50 --concurrency 10 --fail-rate 0.2 --output-dir /tmp/out
"""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

from collector.fetcher import collect
from collector.report import write_csv
from collector.simserver import TelemetrySimulator
from collector.stats import overall, summarize


async def run_collection(args: argparse.Namespace) -> dict:
    """起模拟服务器 → 采集 → 汇总 → 写报表，返回统计信息。"""
    sim = TelemetrySimulator(
        n_vehicles=args.vehicles,
        latency_ms=args.latency_ms,
        fail_rate=args.fail_rate,
        seed=args.seed,
    )
    await sim.start()
    try:
        vehicle_ids = sim.vehicle_ids
        print(
            f"模拟服务器就绪: {sim.base_url}（{len(vehicle_ids)} 辆车，"
            f"延迟 {args.latency_ms}ms，失败率 {args.fail_rate}）"
        )

        t0 = time.perf_counter()
        results = await collect(
            sim.base_url,
            vehicle_ids,
            max_concurrency=args.concurrency,
            max_retries=args.max_retries,
        )
        elapsed = time.perf_counter() - t0

        stats = overall(results)
        out_path = write_csv(results, Path(args.output_dir) / "telemetry_report.csv")
        print(f"\n采集完成: {stats.total} 辆车，耗时 {elapsed:.2f}s")
        print(
            f"成功 {stats.success} / 失败 {stats.failed}"
            f"（成功率 {stats.success_rate_pct}%），平均耗时 {stats.avg_elapsed_ms}ms"
        )
        print(f"报表: {out_path}")

        # 失败清单打印前 5 条
        fails = [s.vehicle_id for s in summarize(results) if not s.ok]
        if fails:
            shown = ", ".join(fails[:5]) + ("..." if len(fails) > 5 else "")
            print(f"失败车辆（重试耗尽）: {shown}")
        return {
            "total": stats.total,
            "success": stats.success,
            "failed": stats.failed,
            "elapsed": round(elapsed, 2),
        }
    finally:
        await sim.stop()  # 产物纪律：无论成败都关服务器


def run_demo() -> None:
    """离线自检：全流程跑通 + 断言正确性（供 README 与验收使用）。"""

    async def _demo() -> None:
        sim = TelemetrySimulator(n_vehicles=10, latency_ms=10, fail_rate=0.0, seed=1)
        await sim.start()
        try:
            results = await collect(sim.base_url, sim.vehicle_ids, max_concurrency=5)
            stats = overall(results)
            assert stats.total == 10 and stats.success == 10, "全成功场景断言失败"
            assert all(r.attempts == 1 for r in results), "无失败时不应重试"
            assert all(r.speed is not None for r in results), "遥测值不应为空"
        finally:
            await sim.stop()
        print("--demo 自检通过: 10/10 采集成功、无重试、遥测值完整")

    asyncio.run(_demo())


def main() -> None:
    parser = argparse.ArgumentParser(description="异步遥测采集服务")
    parser.add_argument("--vehicles", type=int, default=20, help="模拟车辆数（默认 20）")
    parser.add_argument("--concurrency", type=int, default=5, help="采集并发上限（默认 5）")
    parser.add_argument("--max-retries", type=int, default=3, help="单辆车最大重试次数（默认 3）")
    parser.add_argument("--fail-rate", type=float, default=0.1, help="模拟失败率 0~1（默认 0.1）")
    parser.add_argument("--latency-ms", type=float, default=20.0, help="服务端延迟毫秒（默认 20）")
    parser.add_argument("--output-dir", default="/tmp/async-collector-out", help="报表输出目录")
    parser.add_argument("--seed", type=int, default=42, help="模拟随机种子（默认 42）")
    parser.add_argument("--demo", action="store_true", help="离线自检")
    args = parser.parse_args()

    if args.demo:
        run_demo()
        return
    asyncio.run(run_collection(args))


if __name__ == "__main__":
    main()
