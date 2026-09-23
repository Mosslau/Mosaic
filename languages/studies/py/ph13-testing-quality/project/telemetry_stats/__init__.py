"""telemetry_stats —— 设备遥测数据处理库（ph13 测试与工程质量阶段项目）。

职责：CSV 解析清洗 → 按设备分组统计 → CSV 报表 + 文本汇总。
全部函数带完整类型注解（mypy 严格模式通过），配套 pytest 测试与 ruff/black 门禁。
"""

from .parser import TelemetryRow, parse_csv, parse_row
from .stats import DeviceStats, filter_device, per_device_stats

__all__ = [
    "TelemetryRow",
    "parse_csv",
    "parse_row",
    "DeviceStats",
    "filter_device",
    "per_device_stats",
]
__version__ = "0.1.0"
