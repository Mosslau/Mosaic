"""本文件模块职责：FastAPI/Uvicorn 服务启动入口模块。

本模块读取部署配置并启动 HTTP API 进程，不承担长期 Agent 任务执行；生产环境应将 API 进程与独立 Worker 进程分开部署。
"""

import uvicorn

from data_agent_runtime.api import app
from data_agent_runtime.config import get_settings
from data_agent_runtime.runtime.observability import configure_observability


def main() -> None:
    """处理“main”业务步骤，完成输入校验、依赖调用和结果返回。"""
    settings = get_settings()
    if settings.runtime_mode not in {"api", "all"}:
        raise RuntimeError(
            "RUNTIME_MODE must be 'api' or 'all' when starting data-agent-runtime"
        )
    configure_observability(settings, role="api")
    # 禁用 Uvicorn 默认 logging dictConfig，避免它覆盖 Runtime 已配置的
    # JSON Formatter 和脱敏 Handler。HTTP 访问日志由 FastAPI Middleware
    # 统一输出，避免同时出现一份未脱敏/格式不一致的 access log。
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        log_config=None,
        access_log=False,
        # 等待在途 HTTP 请求完成；与 Worker 的 shutdown_timeout 共用同一预算语义。
        timeout_graceful_shutdown=int(settings.shutdown_timeout_seconds),
    )


if __name__ == "__main__":
    main()
