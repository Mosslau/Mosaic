"""本文件模块职责：独立 Worker 进程启动入口模块。

本模块初始化共享 Runtime 资源并启动 TaskWorker，负责消费 Redis Stream 任务；它不提供对外 HTTP API，生产部署应与 API 进程分别扩缩容。
"""

import asyncio
import logging
import signal

from data_agent_runtime.config import get_settings
from data_agent_runtime.runtime.bootstrap import runtime_resources
from data_agent_runtime.runtime.files import RuntimeFileStore
from data_agent_runtime.runtime.metrics import configure_metrics
from data_agent_runtime.runtime.observability import configure_observability
from data_agent_runtime.runtime.worker import create_worker


def main() -> None:
    """处理“main”业务步骤，完成输入校验、依赖调用和结果返回。"""
    asyncio.run(_run())


async def _run() -> None:
    """执行“_run”内部辅助步骤，完成必要的校验、转换和资源处理。"""
    settings = get_settings()
    if settings.runtime_mode not in {"worker", "all"}:
        raise RuntimeError(
            "RUNTIME_MODE must be 'worker' or 'all' when starting data-agent-worker"
        )
    configure_observability(settings, role="worker")
    configure_metrics(settings)
    async with runtime_resources(settings) as resources:
        worker = create_worker(
            settings,
            redis=resources.redis,
            events=resources.events,
            history=resources.history,
            memories=resources.memories,
            checkpointer=resources.checkpointer,
            run_state=resources.run_state,
            store=resources.store,
            files=RuntimeFileStore(resources.redis, settings),
        )
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, worker.stop)

        # serve() 负责 drain：停止领取新任务、等待在跑的 Run、超时后取消并留给重投递。
        await worker.serve(shutdown_timeout=settings.shutdown_timeout_seconds)
        logging.getLogger(__name__).info("Agent worker stopped")


if __name__ == "__main__":
    main()
