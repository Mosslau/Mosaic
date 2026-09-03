# project/streamlog/__init__.py —— streamlog 包：流式日志处理器（ph17 阶段项目）
# 验证环境（目标）：Python 3.13.9 + pytest 8 + ruff 0.12（本机需自行安装）
# 运行/测试/lint：见 project/README.md
#   （python3 -m streamlog.cli / python3 -m pytest / ruff check .）
# 验证状态：已验证（Python 3.13.9 本机实测：project/tests 全绿、ruff 全绿）
"""streamlog —— ph17 阶段项目：流式日志处理器。

四层协议合流（主文档第 3 章）：
- reader / parser：生成器管线，流式解析，内存与文件大小无关（主文档 3.1/3.2）；
- filters：装饰器横切统计 Counted（主文档 3.3）；
- sinks：上下文管理器管理输出资源（主文档 3.4）；
- parser.LogRecord：dataclass 结构化记录（主文档 3.8）。
"""

__version__ = "0.1.0"
