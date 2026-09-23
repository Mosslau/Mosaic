"""模拟遥测服务器：提供设备列表与单设备遥测两个 HTTP 接口。

用 aiohttp web 在**进程内**起服务（不占外部端口约定、测完即停），
延迟与失败率可注入，随机数可播种 —— 测试与演示完全确定性、可复现。
"""

from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime

from aiohttp import web


def make_device_ids(n: int) -> list[str]:
    """生成 n 个设备 id：EV-001 ~ EV-{n}（三位零填充）。"""
    return [f"EV-{i:03d}" for i in range(1, n + 1)]


class TelemetrySimulator:
    """进程内模拟遥测服务器。

    - GET /api/devices                  → {"devices": ["EV-001", ...]}
    - GET /api/devices/{vid}/telemetry  → 200 遥测 JSON，或按 fail_rate 返回 503

    用法（asyncio 上下文内）：

        sim = TelemetrySimulator(latency_ms=20, fail_rate=0.1)
        await sim.start()
        base = sim.base_url          # 实际绑定端口在 start 后确定
        ...
        await sim.stop()
    """

    def __init__(
        self,
        devices: list[str] | None = None,
        n_devices: int = 20,
        latency_ms: float = 0.0,
        fail_rate: float = 0.0,
        seed: int = 42,
    ) -> None:
        self._devices = devices if devices is not None else make_device_ids(n_devices)
        self.latency_ms = latency_ms
        self.fail_rate = fail_rate
        self._rng = random.Random(seed)  # 播种：同一 seed 下失败序列完全可复现
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self.port: int | None = None

    @property
    def device_ids(self) -> list[str]:
        return list(self._devices)

    @property
    def base_url(self) -> str:
        assert self.port is not None, "start() 之后才能取 base_url"
        return f"http://127.0.0.1:{self.port}"

    async def start(self) -> TelemetrySimulator:
        app = web.Application()
        app.router.add_get("/api/devices", self._list_devices)
        app.router.add_get("/api/devices/{vid}/telemetry", self._telemetry)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        # 端口 0 = 系统分配临时端口；start 后从底层 socket 读出实际端口号
        self._site = web.TCPSite(self._runner, "127.0.0.1", 0)
        await self._site.start()
        self.port = self._site._server.sockets[0].getsockname()[1]
        return self

    async def stop(self) -> None:
        """产物纪律：测完必须调用 —— 关掉 aiohttp runner，不残留端口占用。"""
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def _list_devices(self, request: web.Request) -> web.Response:
        return web.json_response({"devices": self._devices})

    async def _telemetry(self, request: web.Request) -> web.Response:
        vid = request.match_info["vid"]
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000)  # 模拟服务端处理耗时
        if self._rng.random() < self.fail_rate:  # 按注入的失败率返回 503
            return web.json_response({"error": "busy"}, status=503)
        return web.json_response(
            {
                "device_id": vid,
                "ts": datetime.now(UTC).isoformat(),
                "speed": round(self._rng.uniform(20.0, 120.0), 1),
                "component": round(self._rng.uniform(40.0, 100.0), 1),
            }
        )
