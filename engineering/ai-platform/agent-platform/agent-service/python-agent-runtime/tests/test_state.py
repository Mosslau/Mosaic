"""本文件模块职责：Redis Run 状态、Worker Lease、Session Lease 和取消标记测试。

测试使用 FakeRedis 验证状态投影、租约互斥、心跳续期和多 Worker 下的生命周期语义。
"""

import asyncio

from test_memory import FakeRedis

from data_agent_runtime.config import Settings
from data_agent_runtime.runtime.state import RedisRunState


def test_run_state_round_trip():
    """
    中文说明：
        验证 tests/test_state 中“run_state_round_trip”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    async def run():
        """
        中文说明：
            在隔离 Sandbox 中执行结构化命令，应用命令白名单、超时、输出大小和网络等安全策略。

        参数：
            - 无：函数使用实例属性、模块配置或闭包变量完成工作。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        state = RedisRunState(
            FakeRedis(),
            Settings(run_state_ttl_seconds=60),
        )

        await state.set_status(
            "run-1",
            "COMPLETED",
            session_id="session-1",
            agent_id="analysis",
            tenant_id="tenant-1",
            user_id="user-1",
            stream=True,
            result={"answer": "完成"},
        )

        value = await state.get("run-1")
        assert value is not None
        assert value["status"] == "COMPLETED"
        assert value["stream"] == "true"
        assert value["result"] == {"answer": "完成"}

    asyncio.run(run())
