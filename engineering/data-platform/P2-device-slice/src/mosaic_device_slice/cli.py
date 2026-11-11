"""纵切入口：跑一条「原始帧 → Kafka → 解码 → PG → 故障/账本」的端到端链路。"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from . import pipeline
from .registry import ProtocolRegistry
from .simulator import simulate


def _fail(message: str) -> int:
    print("[slice] ERROR: %s" % message, file=sys.stderr)
    return 1


def run(args: argparse.Namespace) -> Dict[str, Any]:
    registry = ProtocolRegistry.load(args.registry)
    run_id = pipeline.new_run_id()
    if args.start:
        start = args.start
    else:
        # 每次 run 用不同起始时间：否则 (device, signal, ts) 主键会与历史批次冲突
        offset = int(run_id.rsplit("-", 1)[-1], 16) % 3600
        start = (datetime.now(timezone.utc) + timedelta(seconds=offset)).isoformat(timespec="seconds").replace("+00:00", "Z")
    frames = simulate(devices=args.devices, frames=args.frames, signals=args.signals, seed=args.seed, start=start)
    trace_id = "trace-slice-" + run_id
    topic = "mosaic.device.frames." + run_id

    raw_path = pipeline.write_raw(run_id, frames)
    print("[raw] %s (%d frames)" % (raw_path, len(frames)))

    pipeline.kafka_create_topic(topic)
    produced = pipeline.kafka_produce(topic, frames)
    consumed = pipeline.kafka_consume(topic, expected=len(frames), timeout_ms=args.timeout_ms)
    print("[kafka] topic=%s produced=%d consumed=%d" % (topic, produced, len(consumed)))
    if len(consumed) != len(frames):
        raise RuntimeError("Kafka 消费数量不符：期望 %d，实际 %d" % (len(frames), len(consumed)))

    pipeline.psql(pipeline.DDL)
    pipeline.ledger("raw", trace_id, {"frames": len(frames), "path": str(raw_path)})
    pipeline.ledger("kafka.produce", trace_id, {"topic": topic, "frames": produced})
    pipeline.ledger("kafka.consume", trace_id, {"topic": topic, "frames": len(consumed)})

    rows, events = pipeline.decode_frames(consumed, registry)
    attempted = pipeline.load_signals(rows, trace_id)
    attempted_faults = pipeline.load_faults(events, trace_id)
    loaded = int(pipeline.pg_query("select count(*) from signal_long where trace_id='%s'" % trace_id))
    faults = int(pipeline.pg_query("select count(*) from fault_events where trace_id='%s'" % trace_id))
    pipeline.ledger("decode", trace_id, {"rows": len(rows), "protocols": sorted({r["protocol_version"] for r in rows})})
    pipeline.ledger("load", trace_id, {"attempted_rows": attempted, "inserted_rows": loaded, "attempted_faults": attempted_faults, "inserted_faults": faults})
    print("[pg] signal_rows=%d (attempted %d) fault_events=%d (attempted %d)" % (loaded, attempted, faults, attempted_faults))

    before = loaded
    pipeline.load_signals(rows, trace_id)  # 重放同一批：验证幂等（V3-3 的最小证据）
    after = int(pipeline.pg_query("select count(*) from signal_long where trace_id='%s'" % trace_id))
    pipeline.ledger("replay", trace_id, {"before": before, "after": after, "idempotent": before == after})
    print("[idempotency] before=%d after=%d unchanged=%s" % (before, after, before == after))

    version = pipeline.version_binding_check(consumed[0], registry)
    pipeline.ledger("version_check", trace_id, version)
    print(
        "[version] raw=%d v1=%.3f v2=%.3f differs=%s"
        % (version["raw"], version["v1_value"], version["v2_value"], version["differs"])
    )

    fault_rows = pipeline.pg_query(
        "select device_id || ':' || fault_code || ':' || ts from fault_events where trace_id='%s' order by ts" % trace_id
    )
    summary = {
        "run_id": run_id,
        "trace_id": trace_id,
        "topic": topic,
        "start": consumed[0]["ts"],
        "frames": len(frames),
        "signal_rows": loaded,
        "attempted_rows": attempted,
        "fault_events": faults,
        "attempted_faults": attempted_faults,
        "faults": [line for line in fault_rows.splitlines() if line],
        "idempotent": before == after,
        "version_binding": version,
    }
    print("[summary] " + json.dumps(summary, ensure_ascii=False))
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Mosaic 设备数据最小纵切")
    parser.add_argument("--devices", type=int, default=10)
    parser.add_argument("--frames", type=int, default=10)
    parser.add_argument("--signals", type=int, default=50)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--registry", default=None)
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--start", default=None, help="模拟起始时间（默认当前 UTC 秒）")
    args = parser.parse_args(argv)

    try:
        run(args)
        return 0
    except Exception as exc:  # 基础设施/链路错误统一给出可操作提示
        return _fail("%s\n  先确认底座已起：engineering/infra/compose/up.sh" % exc)


if __name__ == "__main__":
    sys.exit(main())
