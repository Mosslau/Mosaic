# project/vehdash/__init__.py —— vehdash 包入口
# 验证环境：Python 3.13 + pandas 2.x/3.x + matplotlib；本机实测 Python 3.13.12
"""vehdash：车辆遥测 Dashboard（ph18 综合项目）。

一条可复用的「清洗 → 分析 → 报表」流水线：输出自包含 HTML Dashboard +
结构化 JSON 摘要。分析函数为纯函数（可单测），展示层在 report.py。
"""

__version__ = "0.1.0"

from vehdash.analyze import fleet_summary, vehicle_summary
from vehdash.clean import clean_fleet
from vehdash.report import build_dashboard

__all__ = ["clean_fleet", "fleet_summary", "vehicle_summary", "build_dashboard"]
