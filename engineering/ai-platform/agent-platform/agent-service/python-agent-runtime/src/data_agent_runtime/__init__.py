"""本文件模块职责：data-agent-runtime Python 包的顶层初始化模块。

本模块声明 Runtime 包版本和公开的基础包信息，不负责创建网络连接、Worker、模型客户端或其他有副作用的运行资源。

DeepAgents runtime for the data intelligence assistant platform.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
