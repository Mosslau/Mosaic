"""JSONL 账本：D1 的「账本最小版」。

一条事件一行，字段固定：ts / trace_id / event / detail。
不做轮转、不做索引——D1 只证明「调用可追溯」，规模化留给 D11。
"""

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class JsonlLedger:
    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, trace_id: str, event: str, detail: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        record = {
            "ts": _now(),
            "trace_id": trace_id,
            "event": event,
            "detail": detail or {},
        }
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return record

    def read(self, trace_id: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        events: List[Dict[str, Any]] = []
        with self._lock:
            with open(self.path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if trace_id and record.get("trace_id") != trace_id:
                        continue
                    events.append(record)
        return events[-limit:]
