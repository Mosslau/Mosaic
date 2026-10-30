"""本文件模块职责：Redis 会话历史、长期记忆和 Prompt 上下文测试。

测试使用 FakeRedis 验证租户/会话隔离、消息数量限制、记忆注入和摘要相关上下文行为。
"""

import asyncio

from data_agent_runtime.config import Settings
from data_agent_runtime.prompts.analysis import build_analysis_prompt
from data_agent_runtime.runtime.memory import (
    RedisConversationHistory,
    RedisLongTermMemory,
)


class FakePipeline:
    """模拟 Redis Pipeline，记录批量写入操作而不连接真实 Redis。"""
    def __init__(self, redis):
        """
        中文说明：
            初始化 FakePipeline，保存依赖对象、运行配置和后续方法所需的生命周期状态。

        参数：
            - redis: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        self.redis = redis
        self.commands = []

    def delete(self, key):
        """
        中文说明：
            实现 FakePipeline 的“delete”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

        参数：
            - key: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        self.commands.append(("delete", key))
        return self

    def rpush(self, key, *values):
        """
        中文说明：
            实现 FakePipeline 的“rpush”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

        参数：
            - key: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - *values: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        self.commands.append(("rpush", key, values))
        return self

    async def execute(self):
        """
        中文说明：
            实现 FakePipeline 的“execute”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

        参数：
            - 无：函数使用实例属性、模块配置或闭包变量完成工作。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        for command in self.commands:
            if command[0] == "delete":
                self.redis.values.pop(command[1], None)
            else:
                self.redis.values.setdefault(command[1], []).extend(command[2])
        return []


class FakeRedis:
    """模拟 Memory 测试所需的 Redis 数据结构和 Pipeline 行为。"""
    def __init__(self):
        """
        中文说明：
            初始化 FakeRedis，保存依赖对象、运行配置和后续方法所需的生命周期状态。

        参数：
            - 无：函数使用实例属性、模块配置或闭包变量完成工作。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        self.values = {}

    async def lrange(self, key, start, end):
        """
        中文说明：
            实现 FakeRedis 的“lrange”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

        参数：
            - key: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - start: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - end: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        values = self.values.get(key, [])
        return values[start : end + 1 if end >= 0 else None]

    async def rpush(self, key, *values):
        """
        中文说明：
            实现 FakeRedis 的“rpush”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

        参数：
            - key: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - *values: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        self.values.setdefault(key, []).extend(values)

    async def ltrim(self, key, start, end):
        """
        中文说明：
            实现 FakeRedis 的“ltrim”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

        参数：
            - key: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - start: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - end: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        values = self.values.get(key, [])
        self.values[key] = values[start : end + 1 if end >= 0 else None]

    async def delete(self, key):
        """
        中文说明：
            实现 FakeRedis 的“delete”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

        参数：
            - key: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        self.values.pop(key, None)

    async def hgetall(self, key):
        """
        中文说明：
            实现 FakeRedis 的“hgetall”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

        参数：
            - key: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        value = self.values.get(key, {})
        return dict(value) if isinstance(value, dict) else {}

    async def hset(self, key, mapping=None, **kwargs):
        """
        中文说明：
            实现 FakeRedis 的“hset”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

        参数：
            - key: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - mapping: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - **kwargs: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        values = self.values.setdefault(key, {})
        if not isinstance(values, dict):
            values = {}
            self.values[key] = values
        values.update(mapping or {})
        values.update(kwargs)
        return len(mapping or {}) + len(kwargs)

    async def expire(self, key, seconds):
        """
        中文说明：
            实现 FakeRedis 的“expire”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

        参数：
            - key: 未声明类型：由调用方传入，用于完成本函数的核心处理。
            - seconds: 未声明类型：由调用方传入，用于完成本函数的核心处理。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        return key in self.values

    def pipeline(self):
        """
        中文说明：
            实现 FakeRedis 的“pipeline”业务步骤，负责处理输入、调用下层依赖并返回可供上层继续编排的结果。

        参数：
            - 无：函数使用实例属性、模块配置或闭包变量完成工作。

        返回：
            根据具体分支返回结果或抛出异常。

        异常与边界：
            外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
        """
        return FakePipeline(self)


def test_conversation_history_round_trip():
    """
    中文说明：
        验证 tests/test_memory 中“conversation_history_round_trip”这一行为，确保协议、状态变化和异常边界符合预期。

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
        redis = FakeRedis()
        history = RedisConversationHistory(
            redis,
            Settings(conversation_history_max_messages=10),
        )

        await history.append_message(
            session_id="session-1",
            run_id="run-1",
            role="user",
            content="你好",
        )
        await history.append_message(
            session_id="session-1",
            run_id="run-1",
            role="assistant",
            content="你好，有什么可以帮你？",
        )

        messages = await history.list_messages("session-1")
        assert [item["role"] for item in messages] == ["user", "assistant"]
        assert messages[0]["content"] == "你好"

        await history.clear("session-1")
        assert await history.list_messages("session-1") == []

    asyncio.run(run())


def test_long_term_memory_upsert_and_delete():
    """
    中文说明：
        验证 tests/test_memory 中“long_term_memory_upsert_and_delete”这一行为，确保协议、状态变化和异常边界符合预期。

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
        redis = FakeRedis()
        memory = RedisLongTermMemory(redis, Settings(long_term_memory_max_items=10))
        item = {
            "memory_id": "m-1",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "memory_type": "preference",
            "key": "default_time_range",
            "content": "最近 30 天",
        }

        await memory.upsert(item)
        values = await memory.list_memories("tenant-1", "user-1")
        assert values[0]["key"] == "default_time_range"
        assert await memory.delete("tenant-1", "user-1", "m-1") is True
        assert await memory.list_memories("tenant-1", "user-1") == []

    asyncio.run(run())


def test_prompt_contains_controlled_memory():
    """
    中文说明：
        验证 tests/test_memory 中“prompt_contains_controlled_memory”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    prompt = build_analysis_prompt(
        "负责数据分析",
        [],
        [{"key": "default_time_range", "content": "最近 30 天"}],
    )
    assert "受控长期记忆" in prompt
    assert "最近 30 天" in prompt
