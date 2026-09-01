"""telemetry_stats —— 车辆遥测数据处理库（ph13 测试与工程质量阶段项目）。

职责：CSV 解析清洗 → 按车辆分组统计 → CSV 报表 + 文本汇总。
全部函数带完整类型注解（mypy 严格模式通过），配套 pytest 测试与 ruff/black 门禁。
"""

from .parser import TelemetryRow, parse_csv, parse_row
from .stats import VehicleStats, filter_vehicle, per_vehicle_stats

__all__ = [
    "TelemetryRow",
    "parse_csv",
    "parse_row",
    "VehicleStats",
    "filter_vehicle",
    "per_vehicle_stats",
]
__version__ = "0.1.0"
