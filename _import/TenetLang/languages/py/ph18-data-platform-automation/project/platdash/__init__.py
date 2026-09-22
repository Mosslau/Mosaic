# project/platdash/__init__.py —— platdash 包入口
# 验证环境：Python 3.13 + pandas 2.x/3.x + matplotlib；本机实测 Python 3.13.12
"""platdash：平台指标 Dashboard（ph18 综合项目）。

一条可复用的「清洗 → 分析 → 报表」流水线：输出自包含 HTML Dashboard +
结构化 JSON 摘要。分析函数为纯函数（可单测），展示层在 report.py。
"""

__version__ = "0.1.0"

from platdash.analyze import platform_summary, service_summary
from platdash.clean import clean_platform
from platdash.report import build_dashboard

__all__ = ["clean_platform", "platform_summary", "service_summary", "build_dashboard"]
