"""协议登记簿：按「当时的版本」解码，而不是按最新版本。

这是车联网/机器人增量的第一性设计（见技术增量 §3.2）：同一条报文在
不同协议版本下含义不同，历史数据必须按当时的版本解释。
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "registry" / "protocols.json"


class ProtocolRegistry:
    def __init__(self, document: Dict[str, Any]):
        self.document = document
        self.codec_version = document.get("codec_version", "codec-1")
        self.protocols: Dict[str, Any] = document["protocols"]

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "ProtocolRegistry":
        target = Path(path) if path else DEFAULT_REGISTRY_PATH
        with open(target, "r", encoding="utf-8") as handle:
            return cls(json.load(handle))

    def versions(self) -> List[str]:
        return sorted(self.protocols)

    def rule_for(self, version: str, signal_id: str) -> Dict[str, Any]:
        spec = self.protocols.get(version)
        if spec is None:
            raise KeyError("unknown protocol version: %s" % version)
        rule: Dict[str, Any] = dict(spec.get("defaults", {}))
        rule.update(spec.get("signals", {}).get(signal_id, {}))
        return rule

    def decode_value(self, version: str, signal_id: str, raw: int) -> Dict[str, Any]:
        rule = self.rule_for(version, signal_id)
        value = raw * float(rule.get("scale", 1)) + float(rule.get("offset", 0))
        quality = "ok"
        raw_min = rule.get("raw_min")
        raw_max = rule.get("raw_max")
        if raw_min is not None and raw < raw_min:
            quality = "suspect"
        if raw_max is not None and raw > raw_max:
            quality = "suspect"
        return {"value": round(value, 6), "unit": rule.get("unit", "raw"), "quality": quality}

    def decode_frame(self, frame: Dict[str, Any], force_version: Optional[str] = None) -> List[Dict[str, Any]]:
        """frame.protocol 决定用哪个版本；force_version 仅用于「换版验证」演示。"""
        version = force_version or frame.get("protocol")
        if version not in self.protocols:
            raise KeyError("frame %s has unknown protocol %r" % (frame.get("device_id"), version))
        rows = []
        for signal_id, raw in sorted(frame.get("signals", {}).items()):
            decoded = self.decode_value(version, signal_id, raw)
            rows.append(
                {
                    "device_id": frame["device_id"],
                    "signal_id": signal_id,
                    "ts": frame["ts"],
                    "raw": raw,
                    "value": decoded["value"],
                    "unit": decoded["unit"],
                    "quality": decoded["quality"],
                    "protocol_version": version,
                    "codec_version": self.codec_version,
                }
            )
        return rows


def decode_values(frame: Dict[str, Any], registry: ProtocolRegistry, force_version: Optional[str] = None) -> Dict[str, float]:
    return {row["signal_id"]: row["value"] for row in registry.decode_frame(frame, force_version)}
