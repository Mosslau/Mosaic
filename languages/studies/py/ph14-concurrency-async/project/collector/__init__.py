"""collector —— ph14 阶段项目「异步遥测采集服务」的采集包。

包含四个模块：
- simserver：模拟遥测服务器（aiohttp web，可注入延迟/失败率，确定性随机）
- fetcher：aiohttp 并发采集（Semaphore 限速 + 指数退避重试）
- stats：采集结果汇总
- report：CSV 报表输出
"""

__version__ = "0.1.0"
