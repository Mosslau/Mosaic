"""AI 平台 D1 契约：AssetRef / Answer / Service / Ledger / RuntimePort。

字段口径来自 `engineering/ai-platform/AI平台建设路线.md` §3「核心契约」。
"""

from mosaic_kernel.contracts import ContractSet

AI_SPECS = {
    "AssetRef": {
        "required": ["asset_id", "kind", "version", "uri"],
        "properties": {
            "asset_id": {"type": "string", "min_length": 1},
            "kind": {"type": "string", "enum": ["corpus", "dataset", "index", "model", "adapter"]},
            "version": {"type": "string", "min_length": 1},
            "uri": {"type": "string", "min_length": 1},
            "snapshot_id": {"type": ["string", "null"]},
            "digest": {"type": ["string", "null"]},
            "owner": {"type": ["string", "null"]},
        },
    },
    "Answer": {
        "required": ["text", "citations", "confidence"],
        "properties": {
            "text": {"type": "string", "min_length": 1},
            "citations": {"type": "array", "items": {"type": "object"}},
            "confidence": {"type": "number"},
            "no_evidence": {"type": "boolean"},
            "model": {"type": ["string", "null"]},
            "trace_id": {"type": ["string", "null"]},
        },
    },
    "Service": {
        "required": ["name", "version", "endpoint", "health"],
        "properties": {
            "name": {"type": "string", "min_length": 1},
            "version": {"type": "string", "min_length": 1},
            "endpoint": {"type": "string", "min_length": 1},
            "health": {"type": "string", "enum": ["healthy", "degraded", "down"]},
            "runtime": {"type": ["string", "null"]},
            "owner": {"type": ["string", "null"]},
        },
    },
    "Ledger": {
        "required": ["ledger_id", "run_id", "occurred_at"],
        "properties": {
            "ledger_id": {"type": "string", "min_length": 1},
            "run_id": {"type": "string", "min_length": 1},
            "occurred_at": {"type": "string", "format": "date-time"},
            "tokens_in": {"type": ["integer", "null"]},
            "tokens_out": {"type": ["integer", "null"]},
            "gpu_seconds": {"type": ["number", "null"]},
            "cost_usd": {"type": ["number", "null"]},
            "model": {"type": ["string", "null"]},
        },
    },
    "RuntimePort": {
        "required": ["runtime_id", "version", "capabilities", "endpoint"],
        "properties": {
            "runtime_id": {"type": "string", "min_length": 1},
            "version": {"type": "string", "min_length": 1},
            "capabilities": {"type": "array", "items": {"type": "string"}},
            "endpoint": {"type": "string", "min_length": 1},
            "approval": {"type": "boolean"},
            "sandbox": {"type": "boolean"},
        },
    },
}

CONTRACTS = ContractSet("ai-platform", AI_SPECS)

EXAMPLES = {
    "AssetRef": {
        "asset_id": "corpus.vehicle.manual",
        "kind": "corpus",
        "version": "v3",
        "uri": "s3://mosaic/ai/corpus/vehicle-manual/v3",
        "snapshot_id": "snap-20261111-01",
        "digest": "sha256:9f2c",
    },
    "Answer": {
        "text": "P0A1 可能由电池采样线束松动引起，建议先检查接插件。",
        "citations": [
            {"source_type": "doc", "locator": "manual://battery/p0a1#12", "hash": "sha256:ab12"},
            {"source_type": "workorder", "locator": "workorder:WO-2026-0001"},
        ],
        "confidence": 0.82,
        "no_evidence": False,
        "model": "local-vllm/qwen2.5-7b",
    },
    "Service": {
        "name": "agent-runtime",
        "version": "0.3.0",
        "endpoint": "http://127.0.0.1:18181",
        "health": "healthy",
        "runtime": "agent-core",
    },
    "Ledger": {
        "ledger_id": "ledger-0001",
        "run_id": "run-0001",
        "occurred_at": "2026-11-11T03:00:00Z",
        "tokens_in": 1200,
        "tokens_out": 260,
        "gpu_seconds": 1.8,
        "cost_usd": 0.0031,
        "model": "local-vllm/qwen2.5-7b",
    },
    "RuntimePort": {
        "runtime_id": "agent-core",
        "version": "0.1.0",
        "capabilities": ["publish", "stream", "approval", "sandbox"],
        "endpoint": "http://127.0.0.1:18181",
        "approval": True,
        "sandbox": True,
    },
}
