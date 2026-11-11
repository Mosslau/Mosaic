"""设备模拟器：10 台车 × 10 帧 × 50 信号（1 Hz），确定性种子。

生成的是「原始计数」而不是物理值——物理值必须由协议登记簿解码得到，
这样换版（DBC v1 → v2）时才能看出「同一帧、不同含义」。
"""

import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

SIGNAL_NAMES = ["battery_voltage", "motor_temp", "speed"]


def _ts(start: datetime, offset_seconds: int) -> str:
    return (start + timedelta(seconds=offset_seconds)).isoformat(timespec="seconds").replace("+00:00", "Z")


def simulate(
    devices: int = 10,
    frames: int = 10,
    signals: int = 50,
    seed: int = 7,
    start: str = "2026-11-11T06:00:00Z",
) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    begin = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(timezone.utc)
    out: List[Dict[str, Any]] = []

    for device_index in range(devices):
        device_id = "veh-%04d" % (device_index + 1)
        boot_id = "boot-%02d-%d" % (device_index + 1, seed)
        for seq in range(frames):
            raw: Dict[str, int] = {}
            for signal_index in range(signals):
                if signal_index == 0:
                    raw["battery_voltage"] = 400 + rng.randint(0, 40)
                elif signal_index == 1:
                    raw["motor_temp"] = 100 + rng.randint(0, 60)
                elif signal_index == 2:
                    raw["speed"] = rng.randint(0, 12000)
                else:
                    raw["signal_%02d" % signal_index] = rng.randint(0, 1000)

            # 注入两个确定性故障：电池过压（P0A1）、电机过温（P0A2）
            if device_index == 0 and seq == 5:
                raw["battery_voltage"] = 600
            if device_index == 1 and seq == 7:
                raw["motor_temp"] = 300

            out.append(
                {
                    "device_id": device_id,
                    "boot_id": boot_id,
                    "firmware": "fw-1.0",
                    "protocol": "dbc.v1",
                    "ts": _ts(begin, seq),
                    "seq": seq,
                    "signals": raw,
                }
            )
    return out


def fault_events(frame: Dict[str, Any], values: Dict[str, float]) -> List[Dict[str, Any]]:
    """按解码后的物理值判故障；阈值属于业务规则，不属于登记簿。"""
    events = []
    rules = [
        ("battery_voltage", 58.0, "P0A1", "P1"),
        ("motor_temp", 90.0, "P0A2", "P0"),
    ]
    for signal_id, threshold, code, severity in rules:
        value = values.get(signal_id)
        if value is not None and value >= threshold:
            events.append(
                {
                    "event_id": "%s-%s-%s" % (frame["device_id"], frame["ts"], code),
                    "device_id": frame["device_id"],
                    "fault_code": code,
                    "severity": severity,
                    "ts": frame["ts"],
                    "value": value,
                }
            )
    return events
