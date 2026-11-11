"""数据平台 D1 契约：Envelope / TableRef / MetricDef / MQL / LineageEvent / Policy / QueryRequest。

字段口径来自 `engineering/data-platform/通用数据平台建设路线.md` §2.5「核心契约」。
这里只冻结「结构」，语义与版本策略在 D6/D8 展开。
"""

from mosaic_kernel.contracts import ContractSet

DATA_SPECS = {
    "Envelope": {
        "required": ["source_id", "table", "batch_id", "event_time", "payload"],
        "properties": {
            "source_id": {"type": "string", "min_length": 1},
            "table": {"type": "string", "min_length": 1},
            "batch_id": {"type": "string", "min_length": 1},
            "event_time": {"type": "string", "format": "date-time"},
            "watermark": {"type": ["string", "null"], "format": "date-time"},
            "error_code": {"type": ["string", "null"]},
            "t_device": {"type": ["string", "null"], "format": "date-time"},
            "t_edge": {"type": ["string", "null"], "format": "date-time"},
            "t_ingest": {"type": ["string", "null"], "format": "date-time"},
            "payload": {"type": "object"},
        },
    },
    "TableRef": {
        "required": ["catalog", "namespace", "table"],
        "properties": {
            "catalog": {"type": "string", "min_length": 1},
            "namespace": {"type": "string", "min_length": 1},
            "table": {"type": "string", "min_length": 1},
            "snapshot_id": {"type": ["string", "null"]},
            "partition": {"type": ["string", "null"]},
        },
    },
    "MetricDef": {
        "required": ["metric_id", "name", "definition_version", "expression"],
        "properties": {
            "metric_id": {"type": "string", "min_length": 1},
            "name": {"type": "string", "min_length": 1},
            "definition_version": {"type": "string", "min_length": 1},
            "expression": {"type": "string", "min_length": 1},
            "dimensions": {"type": "array", "items": {"type": "string"}},
            "owner": {"type": ["string", "null"]},
            "status": {"type": "string", "enum": ["draft", "published", "deprecated"]},
        },
    },
    "MQL": {
        "required": ["metrics", "time_range"],
        "properties": {
            "metrics": {"type": "array", "items": {"type": "string"}},
            "filters": {"type": "array", "items": {"type": "object"}},
            "group_by": {"type": "array", "items": {"type": "string"}},
            "time_range": {"type": "object"},
            "limit": {"type": ["integer", "null"]},
        },
    },
    "LineageEvent": {
        "required": ["sources", "target", "operation", "occurred_at"],
        "properties": {
            "sources": {"type": "array", "items": {"type": "object"}},
            "target": {"type": "object"},
            "operation": {"type": "string", "enum": ["ingest", "transform", "publish", "query"]},
            "occurred_at": {"type": "string", "format": "date-time"},
            "job_id": {"type": ["string", "null"]},
        },
    },
    "Policy": {
        "required": ["subject", "resource", "action", "tenant", "purpose"],
        "properties": {
            "subject": {"type": "string", "min_length": 1},
            "resource": {"type": "string", "min_length": 1},
            "action": {"type": "string", "enum": ["read", "write", "query", "export"]},
            "tenant": {"type": "string", "min_length": 1},
            "purpose": {"type": "string", "min_length": 1},
            "expires_at": {"type": ["string", "null"], "format": "date-time"},
        },
    },
    "QueryRequest": {
        "required": ["request_id", "subject", "mql", "purpose"],
        "properties": {
            "request_id": {"type": "string", "min_length": 1},
            "subject": {"type": "string", "min_length": 1},
            "mql": {"type": "object"},
            "purpose": {"type": "string", "min_length": 1},
            "limit": {"type": ["integer", "null"]},
            "trace_id": {"type": ["string", "null"]},
        },
    },
}

CONTRACTS = ContractSet("data-platform", DATA_SPECS)

EXAMPLES = {
    "Envelope": {
        "source_id": "tsp",
        "table": "ods.vehicle_telemetry",
        "batch_id": "20261111T000000Z-0001",
        "event_time": "2026-11-11T00:00:00Z",
        "watermark": "2026-11-11T00:05:00Z",
        "payload": {"vin": "LSV1234567890", "speed_kph": 32},
    },
    "TableRef": {
        "catalog": "iceberg",
        "namespace": "ods",
        "table": "vehicle_telemetry",
        "snapshot_id": "8237645123456789",
    },
    "MetricDef": {
        "metric_id": "metric.vehicle.online_rate",
        "name": "车辆在线率",
        "definition_version": "v1",
        "expression": "count(distinct device_id where online) / count(distinct device_id)",
        "dimensions": ["model", "region"],
        "status": "published",
    },
    "MQL": {
        "metrics": ["metric.vehicle.online_rate"],
        "filters": [{"field": "region", "op": "eq", "value": "cn-east"}],
        "group_by": ["model"],
        "time_range": {"start": "2026-11-01T00:00:00Z", "end": "2026-11-11T00:00:00Z"},
    },
    "LineageEvent": {
        "sources": [{"catalog": "iceberg", "namespace": "ods", "table": "vehicle_telemetry"}],
        "target": {"catalog": "iceberg", "namespace": "dwd", "table": "vehicle_daily"},
        "operation": "transform",
        "occurred_at": "2026-11-11T02:00:00Z",
        "job_id": "job-0001",
    },
    "Policy": {
        "subject": "user:analyst-01",
        "resource": "table:iceberg.dwd.vehicle_daily",
        "action": "query",
        "tenant": "tenant-a",
        "purpose": "analysis",
    },
    "QueryRequest": {
        "request_id": "req-0001",
        "subject": "user:analyst-01",
        "mql": {"metrics": ["metric.vehicle.online_rate"], "time_range": {"start": "2026-11-01T00:00:00Z", "end": "2026-11-11T00:00:00Z"}},
        "purpose": "analysis",
        "limit": 1000,
    },
}
