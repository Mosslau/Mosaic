#!/usr/bin/env python3
# exercises/sol-04-mqtt-service.py —— 参考实现：MQTT 数据采集服务（对应 roadmap §18 练习 4）
# 验证环境（目标）：Python 3.13 + paho-mqtt 2.x（真实 broker 路径）；
#                  本机实测 Python 3.13.12（离线路径，纯标准库）
# 运行（离线演示）：python3 sol-04-mqtt-service.py
# 运行（真实 broker）：python3 sol-04-mqtt-service.py --broker localhost --port 1883
# 测试：python3 -m pytest sol-04-mqtt-service.py -q
# lint：ruff check sol-04-mqtt-service.py
# 验证状态：已验证（离线采集/去重/按日分桶 Python 3.13.12 本机实测：自检与 pytest 全绿）；
#          paho 真实 broker 通道未在本环境验证（需本机 MQTT broker，见 README）
"""MQTT 数据采集服务：在线订阅 → 校验/去重 → 按日分桶 JSONL 落盘。

相对 examples/ex08 的 collector，本解补上生产采集的三个点：**去重**（MQTT QoS1 可能
重复投递）、**按日分桶**（文件无限增长 → 单日一文件，归档友好）、**可观测统计**
（accepted/duplicate/invalid/bad_topic 四类计数可审计）。练习要求见 README.md。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

try:  # 真实 broker 才需要；离线 demo 不依赖
    import paho.mqtt.client as mqtt

    HAVE_MQTT = True
except ModuleNotFoundError:  # pragma: no cover
    mqtt = None  # type: ignore[assignment]
    HAVE_MQTT = False

TOPIC_RE = re.compile(r"^veh/(?P<vin>V\d{3})/telemetry$")
REQUIRED_FIELDS = ("ts", "soc_pct", "pack_temp_c", "pack_current_a", "power_kw")


@dataclass(frozen=True, slots=True)
class Reading:
    vin: str
    ts: float
    soc_pct: float
    pack_temp_c: float
    pack_current_a: float
    power_kw: float

    def to_dict(self) -> dict[str, float | str]:
        return {
            "vin": self.vin,
            "ts": self.ts,
            "soc_pct": self.soc_pct,
            "pack_temp_c": self.pack_temp_c,
            "pack_current_a": self.pack_current_a,
            "power_kw": self.power_kw,
        }


def day_bucket(ts: float) -> str:
    """按 Unix 秒取 UTC 日期桶名：data-YYYYMMDD.jsonl（多车共用一桶）。"""
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y%m%d")


class CollectionService:
    """采集服务核心（与 broker 解耦，可离线单测）：校验 → 去重 → 按日 JSONL 落盘。"""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.stats: Counter[str] = Counter()
        self._seen: set[tuple[str, float]] = set()  # (vin, ts) 去重窗口（演示内存版）

    def _file_for(self, ts: float) -> Path:
        return self.data_dir / f"data-{day_bucket(ts)}.jsonl"

    def handle(self, topic: str, payload: bytes | str) -> Reading | None:
        """broker 回调入口：topic 路由 → JSON/字段/量程校验 → 去重 → 落盘。"""
        match = TOPIC_RE.match(topic)
        if match is None:
            self.stats["bad_topic"] += 1
            return None
        try:
            raw = json.loads(payload.decode() if isinstance(payload, bytes) else payload)
            reading = self._validate(match.group("vin"), raw)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            self.stats["invalid"] += 1
            return None
        key = (reading.vin, round(reading.ts, 3))
        if key in self._seen:
            self.stats["duplicate"] += 1
            return None
        self._seen.add(key)
        self._append(reading)
        self.stats["accepted"] += 1
        return reading

    @staticmethod
    def _validate(vin: str, raw: object) -> Reading:
        if not isinstance(raw, dict) or not all(k in raw for k in REQUIRED_FIELDS):
            raise ValueError("缺字段")
        ts = float(raw["ts"])
        soc = float(raw["soc_pct"])
        temp = float(raw["pack_temp_c"])
        current = float(raw["pack_current_a"])
        power = float(raw["power_kw"])
        if not (
            0 <= soc <= 100
            and -40 <= temp <= 65
            and -300 <= current <= 400
            and -300 <= power <= 300
        ):
            raise ValueError("量程越界")
        return Reading(vin, ts, soc, temp, current, power)

    def _append(self, reading: Reading) -> None:
        with self._file_for(reading.ts).open("a", encoding="utf-8") as f:
            f.write(json.dumps(reading.to_dict(), ensure_ascii=False) + "\n")

    def today_files(self) -> list[Path]:
        return sorted(self.data_dir.glob("data-*.jsonl"))


class MqttRunner:
    """paho 胶水：把 CollectionService 挂到真实 broker（需安装 paho + 本地 broker）。"""

    def __init__(self, service: CollectionService, host: str, port: int) -> None:
        if not HAVE_MQTT:
            raise RuntimeError("需要安装 paho-mqtt：python3 -m pip install 'paho-mqtt>=2'")
        self.service = service
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.host, self.port = host, port

    def _on_connect(self, client: object, userdata: object, flags: object, reason: object) -> None:
        client.subscribe("veh/+/telemetry", qos=1)  # QoS1：至少一次 → 重复靠业务层去重

    def _on_message(self, client: object, userdata: object, message: object) -> None:
        self.service.handle(str(message.topic), bytes(message.payload))

    def run(self) -> None:
        self.client.connect_async(self.host, self.port)
        self.client.loop_start()
        try:
            input("按回车停止采集…\n")
        finally:
            self.client.loop_stop()
            self.client.disconnect()


class FakeBroker:
    """离线通道：直接向服务投递 (topic, payload)，等价于 broker 回调。"""

    def __init__(self, service: CollectionService) -> None:
        self.service = service

    def publish(self, topic: str, payload: str) -> None:
        self.service.handle(topic, payload.encode())


def payload(vin: str, ts: float, **overrides: object) -> str:
    base = {
        "ts": ts,
        "soc_pct": 80.0,
        "pack_temp_c": 30.0,
        "pack_current_a": -25.0,
        "power_kw": -9.6,
    }
    base.update(overrides)
    return json.dumps(base)


def demo(service: CollectionService) -> None:
    broker = FakeBroker(service)
    ts1, ts2, ts3 = 1_700_000_000.0, 1_700_000_060.0, 1_700_000_120.0
    # 合法
    broker.publish("veh/V001/telemetry", payload("V001", ts1))
    broker.publish("veh/V002/telemetry", payload("V002", ts2))
    broker.publish("veh/V003/telemetry", payload("V003", ts3))
    # QoS1 重复投递同一帧（ts 相同）→ 去重
    broker.publish("veh/V001/telemetry", payload("V001", ts1))
    # 非法
    broker.publish("veh/V001/telemetry", payload("V001", ts1 + 1, soc_pct=999))
    broker.publish("veh/V001/telemetry", "bad json")
    broker.publish("veh/V001/events", payload("V001", ts1))  # 错主题


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="MQTT 车联网数据采集服务")
    parser.add_argument("--broker", help="MQTT broker 地址；缺省走离线 demo")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--data-dir", type=Path, default=Path("/tmp/ph18-exer04"))
    args = parser.parse_args(argv)

    service = CollectionService(args.data_dir)
    demo(service)
    print("== 采集审计 ==")
    for key, count in sorted(service.stats.items()):
        print(f"  {key}: {count}")
    files = service.today_files()
    print(f"  落盘文件：{[f.name for f in files]}")

    # ---- 自检 ----
    assert service.stats["accepted"] == 3
    assert service.stats["duplicate"] == 1  # QoS1 重复帧被去重
    assert service.stats["invalid"] == 2
    assert service.stats["bad_topic"] == 1
    assert len(files) == 1 and files[0].name.startswith("data-")
    print("\n自检通过：校验、去重、主题路由、按日分桶断言全绿")

    if args.broker:
        MqttRunner(service, args.broker, args.port).run()


def test_dedup_repeated_delivery() -> None:
    service = CollectionService(Path("/tmp/ph18-exer04-tests/dedup"))
    broker = FakeBroker(service)
    broker.publish("veh/V001/telemetry", payload("V001", 1_700_000_000.0))
    broker.publish("veh/V001/telemetry", payload("V001", 1_700_000_000.0))  # QoS1 重投
    assert service.stats["accepted"] == 1 and service.stats["duplicate"] == 1


def test_day_rotation() -> None:
    service = CollectionService(Path("/tmp/ph18-exer04-tests/rotation"))
    broker = FakeBroker(service)
    broker.publish("veh/V001/telemetry", payload("V001", 1_700_000_000.0))  # 当日
    broker.publish("veh/V001/telemetry", payload("V001", 1_700_086_400.0))  # 次日（+1 天）
    files = {f.name for f in service.today_files()}
    assert len(files) == 2  # 两个日桶


def test_invalid_rejected() -> None:
    service = CollectionService(Path("/tmp/ph18-exer04-tests/invalid"))
    broker = FakeBroker(service)
    broker.publish("veh/V001/telemetry", payload("V001", 1.0, pack_temp_c=200))
    broker.publish("veh/V001/telemetry", "{}")
    assert service.stats["accepted"] == 0 and service.stats["invalid"] == 2


if __name__ == "__main__":
    main(sys.argv[1:])
