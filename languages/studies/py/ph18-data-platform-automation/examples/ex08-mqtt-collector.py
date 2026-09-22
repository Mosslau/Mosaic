#!/usr/bin/env python3
# examples/ex08-mqtt-collector.py —— MQTT 指标采集服务（主文档 3.8）
# 验证环境（目标）：Python 3.13 + paho-mqtt 2.x（真实 broker 路径）
# 运行（离线自检）：python3 ex08-mqtt-collector.py —— 不连 broker，用 Fake 通道跑通采集逻辑
# 运行（真实 broker）：mosquitto 等 broker 起在 localhost:1883 后，改脚本尾部调用 run_realtime()
# 测试：python3 -m pytest ex08-mqtt-collector.py -q
# lint：ruff check ex08-mqtt-collector.py
# 验证状态：已验证（离线采集逻辑，Python 3.13.12 本机实测：自检与 pytest 全绿，paho 2.1.0 已装）；
#          paho 真实 broker 通道**未在本环境验证**（本机无运行中的 MQTT broker，
#          需要 `python3 -m pip install paho-mqtt` + 起 mosquitto 后按 README 复现）
"""MQTT 数据平台采集服务：订阅主题 → 校验载荷 → 落地 sink。

采集链路关注三件事：主题树（Topic Tree）路由、载荷校验（拒收脏数据）、broker 与业务
解耦（sink 可换、可测）。paho 只负责「与 broker 的传输」，本示例把其余全部收敛成可
离线单测的纯逻辑，再用 Fake 通道在无 broker 环境完整演示。
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

try:  # paho 只在真实 broker 路径用到；离线自检不依赖它
    import paho.mqtt.client as mqtt

    HAVE_MQTT = True
except ModuleNotFoundError:  # pragma: no cover —— 依赖缺失时仅影响真实 broker 路径
    mqtt = None  # type: ignore[assignment]
    HAVE_MQTT = False

TOPIC_RE = re.compile(r"^svc/(?P<node_id>V\d{3})/metrics$")
# 真实采集里 NODE_ID 常是 17 位 WMI+VDS+VIS，教学用短 NODE_ID；正则即"主题路由的校验层"

INVALID_PAYLOAD = "invalid_payload"
INVALID_TOPIC = "invalid_topic"


@dataclass(frozen=True, slots=True)
class MetricsReading:
    """一条通过校验的指标：JSON 载荷的最小稳定字段（真实场景会更多）。"""

    node_id: str
    ts: float
    cpu_pct: float
    disk_temp_c: float
    power_w: float

    def to_json_line(self) -> str:
        return json.dumps(
            {
                "node_id": self.node_id,
                "ts": self.ts,
                "cpu_pct": self.cpu_pct,
                "disk_temp_c": self.disk_temp_c,
                "power_w": self.power_w,
            },
            ensure_ascii=False,
        )


class MemorySink:
    """测试/演示用 sink：落内存列表，可断言（真实场景换 JsonlSink / DB / 消息队列）。"""

    def __init__(self) -> None:
        self.items: list[MetricsReading] = []

    def append(self, reading: MetricsReading) -> None:
        self.items.append(reading)


class JsonlSink:
    """生产形态 sink：每条有效读数以 JSONL 追加到文件（写 /tmp，仓库不落数据）。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, reading: MetricsReading) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(reading.to_json_line() + "\n")


class MetricsCollector:
    """采集核心：主题路由 + 载荷校验 + 落 sink。与 broker 无关，可离线单测。"""

    def __init__(self, sink: MemorySink | JsonlSink) -> None:
        self.sink = sink
        self.stats: Counter[str] = Counter()  # 采集审计：有效/无效计数可复现可核对

    def handle_message(self, topic: str, payload: bytes | str) -> MetricsReading | None:
        """broker 回调入口：返回 None 表示拒收（主题不匹配或载荷非法）。"""
        match = TOPIC_RE.match(topic)
        if match is None:
            self.stats[INVALID_TOPIC] += 1
            return None
        try:
            raw = json.loads(payload.decode() if isinstance(payload, bytes) else payload)
            reading = self._validate(match.group("node_id"), raw)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            self.stats[INVALID_PAYLOAD] += 1
            return None
        self.sink.append(reading)
        self.stats["accepted"] += 1
        return reading

    @staticmethod
    def _validate(node_id: str, raw: object) -> MetricsReading:
        """类型收窄式校验：任何一步不符即抛 ValueError，由 handle_message 转拒收。"""
        if not isinstance(raw, dict):
            raise ValueError("载荷必须是 JSON 对象")
        ts = float(raw["ts"])
        soc = float(raw["cpu_pct"])
        temp = float(raw["disk_temp_c"])
        power = float(raw["power_w"])
        if not (0 <= soc <= 100 and -40 <= temp <= 65 and -300 <= power <= 300):
            raise ValueError("量程越界")
        return MetricsReading(node_id=node_id, ts=ts, cpu_pct=soc, disk_temp_c=temp, power_w=power)


class MqttIngest:
    """paho 传输胶水：把 broker 消息桥到 collector（无 broker 环境不可运行）。"""

    def __init__(
        self, collector: MetricsCollector, host: str = "localhost", port: int = 1883
    ) -> None:
        if not HAVE_MQTT:
            raise RuntimeError("需要安装 paho-mqtt：python3 -m pip install 'paho-mqtt>=2'")
        self.collector = collector
        self.host, self.port = host, port
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)  # paho 2.x API
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(
        self, client: object, userdata: object, flags: object, reason_code: object
    ) -> None:
        # 订阅通配主题树：svc/+/metrics 命中所有服务实例；真实场景按需更细粒度
        client.subscribe("svc/+/metrics", qos=1)

    def _on_message(self, client: object, userdata: object, message: object) -> None:
        # paho 2.x 的 Message 对象；此处只依赖 topic 与 payload 两个属性
        self.collector.handle_message(str(message.topic), bytes(message.payload))

    def start(self) -> None:
        self.client.connect_async(self.host, self.port)
        self.client.loop_start()

    def stop(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()


class FakeBroker:
    """离线通道：模拟 broker 把 (topic, payload) 投递给 collector（免网络可复现）。"""

    def __init__(self, collector: MetricsCollector) -> None:
        self.collector = collector

    def publish(self, topic: str, payload: str) -> None:
        self.collector.handle_message(topic, payload.encode())


def main() -> None:
    collector = MetricsCollector(MemorySink())
    broker = FakeBroker(collector)
    # 3 条合法 + 2 条非法 + 1 个错主题 → 统计应精确
    broker.publish(
        "svc/V001/metrics",
        '{"ts": 1700000001, "cpu_pct": 88.0, "disk_temp_c": 31.2, "power_w": -11.5}',
    )
    broker.publish(
        "svc/V002/metrics",
        '{"ts": 1700000002, "cpu_pct": 61.0, "disk_temp_c": 40.1, "power_w": -8.2}',
    )
    broker.publish(
        "svc/V003/metrics",
        '{"ts": 1700000003, "cpu_pct": 12.0, "disk_temp_c": 33.8, "power_w": 3.1}',
    )
    broker.publish("svc/V001/metrics", "not-json")  # 载荷非法
    broker.publish(
        "svc/V001/metrics", '{"ts": "bad", "cpu_pct": 999, "disk_temp_c": 0, "power_w": 0}'
    )  # 量程越界
    broker.publish("svc/V999/log", "{}")  # 主题不匹配（错用 /log 后缀）

    print("== 采集审计统计 ==")
    for key, count in sorted(collector.stats.items()):
        print(f"  {key}: {count}")
    print(f"  落库 {len(collector.sink.items)} 条（类型 {type(collector.sink).__name__}）")

    # 自检
    assert collector.stats["accepted"] == 3
    assert collector.stats[INVALID_PAYLOAD] == 2
    assert collector.stats[INVALID_TOPIC] == 1
    assert [r.node_id for r in collector.sink.items] == ["V001", "V002", "V003"]
    assert all(isinstance(r, MetricsReading) for r in collector.sink.items)

    # 生产形态：换 JsonlSink 重放一次，数据落 /tmp 便于人工复核
    path = Path("/tmp/ph18-ex08/metrics.jsonl")
    path.unlink(missing_ok=True)  # 每次运行从空文件开始，断言才可复现
    jsonl_collector = MetricsCollector(JsonlSink(path))
    FakeBroker(jsonl_collector).publish(
        "svc/V001/metrics",
        '{"ts": 1700000001, "cpu_pct": 88.0, "disk_temp_c": 31.2, "power_w": -11.5}',
    )
    assert path.exists() and len(path.read_text(encoding="utf-8").strip().splitlines()) == 1
    print(f"\nJSONL 样例已写：{path}")
    print("\n自检通过：主题路由、载荷校验、sink 可替换（Memory/Jsonl）全绿")
    print("说明：真实 broker 通道（MqttIngest）未在本环境验证 —— 需本机 MQTT broker。")


def test_topic_routing() -> None:
    collector = MetricsCollector(MemorySink())
    broker = FakeBroker(collector)
    broker.publish("svc/V001/metrics", '{"ts": 1, "cpu_pct": 50, "disk_temp_c": 30, "power_w": -5}')
    broker.publish("svc/V001/wrong-suffix", '{"ts": 1}')
    assert len(collector.sink.items) == 1
    assert collector.sink.items[0].node_id == "V001"
    assert collector.stats[INVALID_TOPIC] == 1


def test_invalid_payload_rejected() -> None:
    collector = MetricsCollector(MemorySink())
    broker = FakeBroker(collector)
    broker.publish("svc/V001/metrics", "oops")  # 非法 JSON
    broker.publish(
        "svc/V001/metrics", '{"ts": "x", "cpu_pct": 0, "disk_temp_c": 0, "power_w": 0}'
    )  # 类型错
    broker.publish(
        "svc/V001/metrics", '{"ts": 1, "cpu_pct": 999, "disk_temp_c": 0, "power_w": 0}'
    )  # 量程越界
    assert collector.sink.items == []
    assert collector.stats[INVALID_PAYLOAD] == 3


def test_collector_audit_counts() -> None:
    collector = MetricsCollector(MemorySink())
    broker = FakeBroker(collector)
    for node_id in ("V001", "V002"):
        broker.publish(
            f"svc/{node_id}/metrics", '{"ts": 1, "cpu_pct": 50, "disk_temp_c": 30, "power_w": -5}'
        )
    assert collector.stats["accepted"] == 2
    assert collector.stats.total() == 2  # 无无效消息时统计干净


if __name__ == "__main__":
    main()
