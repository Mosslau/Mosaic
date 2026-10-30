"""本地测试 MCP Server 和测试 RAG 工具。

本文件用于替代尚未部署的 Java MCP Gateway，给 Python DeepAgents Runtime
提供一个确定性、无外部数据库依赖的 MCP 服务。它同时暴露：

- 元数据工具：``metadata_search``；
- 指标口径工具：``search_metric_definition``；
- SQL 校验工具：``sql_validate``；
- 只读查询工具：``query_readonly``；
- 测试 RAG 检索工具：``search_knowledge``。

启动方式：

    uv run python examples/test_mcp_server.py

默认地址：

    http://127.0.0.1:8810/mcp

该服务只适合本地联调，不提供真实的租户权限、SQL 安全、数据脱敏或审计能力。
生产环境仍应将 run.json 中的 MCP 地址替换为 Java MCP/Data Gateway。
"""

from __future__ import annotations

import argparse
import re
from typing import Any

from mcp.server.fastmcp import FastMCP

# 测试 MCP 服务使用独立端口，避免与 Python Runtime 的 8800 端口冲突。
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8810

mcp = FastMCP(
    name="data-agent-test-mcp",
    instructions=(
        "本服务仅用于 Python Agent Runtime 本地联调，返回固定的车辆域测试元数据、"
        "指标定义、SQL 校验结果、只读查询结果和 RAG 知识片段。"
    ),
    host=DEFAULT_HOST,
    port=DEFAULT_PORT,
    streamable_http_path="/mcp",
    stateless_http=True,
)


# 测试数据字典：模拟 Java 元数据服务返回的结构化结果。
_METADATA: dict[str, dict[str, Any]] = {
    "vehicle_battery": {
        "table": "vehicle_battery",
        "description": "车辆电池遥测数据表",
        "columns": [
            {
                "name": "vehicle_model",
                "type": "string",
                "description": "车型，例如 NQi GT",
            },
            {
                "name": "battery_voltage",
                "type": "decimal(10,2)",
                "unit": "V",
                "description": "电池平均电压",
            },
            {
                "name": "event_time",
                "type": "timestamp",
                "description": "遥测事件时间，UTC",
            },
        ],
    }
}

# 测试指标知识库：search_metric_definition 和 search_knowledge 会从这里检索。
_METRICS: list[dict[str, Any]] = [
    {
        "metric_name": "average_battery_voltage",
        "display_name": "平均电池电压",
        "definition": "在指定时间范围和车型过滤条件下，对 battery_voltage 做算术平均。",
        "unit": "V",
        "grain": "车型 + 时间范围",
        "source_table": "vehicle_battery",
    },
    {
        "metric_name": "battery_voltage_sample_count",
        "display_name": "电池电压样本量",
        "definition": "满足时间范围、车型和非空电池电压条件的遥测记录数。",
        "unit": "条",
        "grain": "车型 + 时间范围",
        "source_table": "vehicle_battery",
    },
]


@mcp.tool()
def metadata_search(query: str, table_name: str | None = None) -> dict[str, Any]:
    """查询测试数据字典、表结构和字段定义。"""
    normalized = (table_name or query or "").lower()
    if "battery" in normalized or "电池" in normalized or "vehicle" in normalized:
        return {"matched": True, "items": [_METADATA["vehicle_battery"]]}
    return {"matched": False, "items": [], "message": "测试数据字典中没有匹配的表。"}


@mcp.tool()
def search_metric_definition(
    query: str,
    metric_name: str | None = None,
) -> dict[str, Any]:
    """检索测试指标口径，作为 RAG 的指标定义检索工具。"""
    text = " ".join(filter(None, [query, metric_name])).lower()
    items = [
        metric
        for metric in _METRICS
        if not text
        or any(
            value in text
            for value in (
                metric["metric_name"].lower(),
                metric["display_name"].lower(),
                "battery",
                "电池",
                "voltage",
                "电压",
            )
        )
    ]
    return {
        "matched": bool(items),
        "items": items,
        "source": "test-metric-catalog",
    }


@mcp.tool()
def search_knowledge(query: str, top_k: int = 3) -> dict[str, Any]:
    """检索测试知识库内容，作为 RAG Retriever 的本地替身。"""
    documents = [
        {
            "id": "kb-vehicle-battery-001",
            "title": "车辆电池电压分析口径",
            "content": (
                "平均电池电压必须限定车型和时间范围，并过滤 battery_voltage IS NOT NULL；"
                "结果单位为 V。"
            ),
            "score": 0.98,
        },
        {
            "id": "kb-data-quality-001",
            "title": "遥测数据质量检查规范",
            "content": "分析平均值时应同时报告样本量、缺失值情况、时间覆盖范围和异常值影响。",
            "score": 0.93,
        },
        {
            "id": "kb-sql-safety-001",
            "title": "只读 SQL 规范",
            "content": "测试查询只允许 SELECT 或 WITH 查询，不允许 INSERT、UPDATE、DELETE、DDL 和多语句执行。",
            "score": 0.90,
        },
    ]
    query_text = query.lower()
    ranked = sorted(
        documents,
        key=lambda item: (
            0 if any(word in item["content"].lower() for word in re.findall(r"\w+", query_text)) else 1,
            -item["score"],
        ),
    )
    return {
        "query": query,
        "items": ranked[: max(1, min(top_k, 10))],
        "source": "test-knowledge-base",
    }


@mcp.tool()
def sql_validate(sql: str) -> dict[str, Any]:
    """校验测试 SQL 是否为单条只读查询。"""
    normalized = sql.strip().lower()
    forbidden = re.search(
        r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke)\b",
        normalized,
    )
    is_readonly = normalized.startswith(("select", "with")) and not forbidden
    return {
        "valid": is_readonly,
        "readonly": is_readonly,
        "normalized_sql": sql.strip(),
        "message": "SQL 通过测试只读校验。" if is_readonly else "只允许单条 SELECT/WITH 查询。",
    }


@mcp.tool()
def query_readonly(sql: str) -> dict[str, Any]:
    """执行一个固定结果的测试只读查询，不访问真实数据库。"""
    validation = sql_validate(sql)
    if not validation["valid"]:
        return {"status": "REJECTED", "validation": validation, "rows": []}
    return {
        "status": "COMPLETED",
        "columns": ["vehicle_model", "average_battery_voltage", "sample_count"],
        "rows": [
            {
                "vehicle_model": "NQi GT",
                "average_battery_voltage": 72.48,
                "sample_count": 1284,
            }
        ],
        "unit": "V",
        "source": "test-readonly-dataset",
        "validation": validation,
    }


def _parse_args() -> argparse.Namespace:
    """解析本地测试服务的启动参数。"""
    parser = argparse.ArgumentParser(description="启动本地测试 MCP/RAG 服务")
    parser.add_argument("--host", default=DEFAULT_HOST, help="监听地址")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="监听端口")
    return parser.parse_args()


def main() -> None:
    """以 Streamable HTTP 方式启动测试 MCP 服务。"""
    args = _parse_args()
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
