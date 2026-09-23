"""simserver 测试：模拟服务器的接口行为与生命周期。"""

from __future__ import annotations

import asyncio

import aiohttp

from collector.simserver import TelemetrySimulator


def test_list_devices():
    async def _t() -> None:
        sim = TelemetrySimulator(devices=["EV-001", "EV-002", "EV-003"])
        await sim.start()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{sim.base_url}/api/devices") as resp:
                    assert resp.status == 200
                    body = await resp.json()
                    assert body["devices"] == ["EV-001", "EV-002", "EV-003"]
        finally:
            await sim.stop()

    asyncio.run(_t())


def test_telemetry_success_when_fail_rate_zero():
    async def _t() -> None:
        sim = TelemetrySimulator(devices=["EV-001"], latency_ms=5, fail_rate=0.0)
        await sim.start()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{sim.base_url}/api/devices/EV-001/telemetry") as resp:
                    assert resp.status == 200
                    body = await resp.json()
                    assert body["device_id"] == "EV-001"
                    assert isinstance(body["speed"], float)
                    assert isinstance(body["component"], float)
        finally:
            await sim.stop()

    asyncio.run(_t())


def test_telemetry_fails_when_fail_rate_one():
    async def _t() -> None:
        sim = TelemetrySimulator(devices=["EV-001"], fail_rate=1.0)
        await sim.start()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{sim.base_url}/api/devices/EV-001/telemetry") as resp:
                    assert resp.status == 503
        finally:
            await sim.stop()

    asyncio.run(_t())


def test_same_seed_is_deterministic():
    """同一 seed 下失败序列完全可复现（供重试测试依赖确定性）。"""

    async def _collect_failures(seed: int) -> list[str]:
        sim = TelemetrySimulator(
            devices=["EV-001", "EV-002", "EV-003", "EV-004"],
            fail_rate=0.5,
            seed=seed,
        )
        await sim.start()
        try:
            async with aiohttp.ClientSession() as session:
                results = []
                for vid in sim.device_ids:
                    async with session.get(f"{sim.base_url}/api/devices/{vid}/telemetry") as resp:
                        results.append((vid, resp.status))
            return [vid for vid, status in results if status == 503]
        finally:
            await sim.stop()

    assert asyncio.run(_collect_failures(7)) == asyncio.run(_collect_failures(7))


def test_stop_is_idempotent():
    async def _t() -> None:
        sim = TelemetrySimulator(devices=["EV-001"])
        await sim.start()
        await sim.stop()
        await sim.stop()  # 第二次 stop 不应抛错

    asyncio.run(_t())
