"""纵切流水线：原始帧落 raw → Kafka → 解码 → PG 长表 + 故障事件 + 账本。

基础设施访问走 `docker compose exec`：D2/D3 阶段还没有引入 Kafka/PG 客户端库，
本单元先用「容器内 CLI」把链路跑通；D3 正式接入时替换为 SeaTunnel/JDBC。
"""

import json
import os
import secrets
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .registry import ProtocolRegistry, decode_values
from .simulator import fault_events

REPO_ROOT = Path(__file__).resolve().parents[5]
COMPOSE_FILE = REPO_ROOT / "engineering" / "infra" / "compose" / "docker-compose.yml"
UNIT_ROOT = REPO_ROOT / "engineering" / "data-platform" / "P2-device-slice"

DDL = """
create table if not exists signal_long (
  device_id text not null,
  signal_id text not null,
  ts timestamptz not null,
  raw integer not null,
  value double precision not null,
  unit text,
  quality text,
  protocol_version text not null,
  codec_version text not null,
  trace_id text,
  primary key (device_id, signal_id, ts)
);
create table if not exists fault_events (
  event_id text primary key,
  device_id text not null,
  fault_code text not null,
  severity text not null,
  ts timestamptz not null,
  value double precision,
  trace_id text
);
create table if not exists pipeline_ledger (
  id bigserial primary key,
  ts timestamptz not null default now(),
  trace_id text not null,
  stage text not null,
  detail jsonb not null
);
"""


def _compose(service: str, *args: str, stdin: Optional[str] = None) -> str:
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "exec", "-T", service] + list(args)
    proc = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "docker compose exec %s failed (%d): %s" % (service, proc.returncode, proc.stderr.strip()[:500])
        )
    return proc.stdout


def kafka_create_topic(topic: str) -> None:
    _compose(
        "kafka",
        "/opt/kafka/bin/kafka-topics.sh",
        "--bootstrap-server", "kafka:9092",
        "--create", "--if-not-exists",
        "--topic", topic,
        "--partitions", "1",
        "--replication-factor", "1",
    )


def kafka_produce(topic: str, frames: Iterable[Dict[str, Any]]) -> int:
    frame_list = list(frames)
    payload = "\n".join(json.dumps(frame, ensure_ascii=False, sort_keys=True) for frame in frame_list) + "\n"
    _compose(
        "kafka",
        "/opt/kafka/bin/kafka-console-producer.sh",
        "--bootstrap-server", "kafka:9092",
        "--topic", topic,
        stdin=payload,
    )
    return len(frame_list)


def kafka_consume(topic: str, expected: int, timeout_ms: int = 30000) -> List[Dict[str, Any]]:
    out = _compose(
        "kafka",
        "/opt/kafka/bin/kafka-console-consumer.sh",
        "--bootstrap-server", "kafka:9092",
        "--topic", topic,
        "--from-beginning",
        "--max-messages", str(expected),
        "--timeout-ms", str(timeout_ms),
    )
    frames = []
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        frames.append(json.loads(line))
    return frames


def psql(sql: str) -> str:
    return _compose(
        "postgres",
        "psql", "-U", "mosaic", "-d", "mosaic",
        "-v", "ON_ERROR_STOP=1", "-q", "-f", "-",
        stdin=sql,
    )


def pg_query(sql: str) -> str:
    return _compose(
        "postgres",
        "psql", "-U", "mosaic", "-d", "mosaic", "-tAc", sql,
    ).strip()


def _quote(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def load_signals(rows: List[Dict[str, Any]], trace_id: str, batch: int = 500) -> int:
    if not rows:
        return 0
    columns = "device_id, signal_id, ts, raw, value, unit, quality, protocol_version, codec_version, trace_id"
    loaded = 0
    for start in range(0, len(rows), batch):
        chunk = rows[start:start + batch]
        values = []
        for row in chunk:
            values.append(
                "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                % (
                    _quote(row["device_id"]),
                    _quote(row["signal_id"]),
                    _quote(row["ts"]),
                    _quote(row["raw"]),
                    _quote(row["value"]),
                    _quote(row.get("unit")),
                    _quote(row.get("quality")),
                    _quote(row["protocol_version"]),
                    _quote(row["codec_version"]),
                    _quote(trace_id),
                )
            )
        psql("insert into signal_long (%s) values %s on conflict (device_id,signal_id,ts) do nothing;\n" % (columns, ",".join(values)))
        loaded += len(chunk)
    return loaded


def load_faults(events: List[Dict[str, Any]], trace_id: str) -> int:
    if not events:
        return 0
    values = []
    for event in events:
        values.append(
            "(%s,%s,%s,%s,%s,%s,%s)"
            % (
                _quote(event["event_id"]),
                _quote(event["device_id"]),
                _quote(event["fault_code"]),
                _quote(event["severity"]),
                _quote(event["ts"]),
                _quote(event["value"]),
                _quote(trace_id),
            )
        )
    psql(
        "insert into fault_events (event_id,device_id,fault_code,severity,ts,value,trace_id) "
        "values %s on conflict (event_id) do nothing;\n" % ",".join(values)
    )
    return len(events)


def write_raw(run_id: str, frames: List[Dict[str, Any]]) -> Path:
    directory = UNIT_ROOT / "var" / "raw" / run_id
    directory.mkdir(parents=True, exist_ok=False)  # raw 只追加：同一 run_id 不允许重写
    path = directory / "frames.jsonl"
    with open(path, "x", encoding="utf-8") as handle:
        for frame in frames:
            handle.write(json.dumps(frame, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def ledger(stage: str, trace_id: str, detail: Dict[str, Any]) -> None:
    psql(
        "insert into pipeline_ledger(trace_id, stage, detail) values (%s,%s,%s::jsonb);\n"
        % (_quote(trace_id), _quote(stage), _quote(json.dumps(detail, ensure_ascii=False)))
    )


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)


def decode_frames(frames: List[Dict[str, Any]], registry: ProtocolRegistry):
    rows: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []
    for frame in frames:
        decoded = registry.decode_frame(frame)
        rows.extend(decoded)
        values = {row["signal_id"]: row["value"] for row in decoded}
        events.extend(fault_events(frame, values))
    return rows, events


def version_binding_check(frame: Dict[str, Any], registry: ProtocolRegistry) -> Dict[str, Any]:
    """同一条报文：按 v1 解 vs 按 v2 解，电池电压必然不同（V3-6 的最小证据）。"""
    v1 = decode_values(frame, registry, force_version="dbc.v1")["battery_voltage"]
    v2 = decode_values(frame, registry, force_version="dbc.v2")["battery_voltage"]
    return {
        "frame_protocol": frame.get("protocol"),
        "raw": frame["signals"]["battery_voltage"],
        "v1_value": v1,
        "v2_value": v2,
        "differs": v1 != v2,
    }
