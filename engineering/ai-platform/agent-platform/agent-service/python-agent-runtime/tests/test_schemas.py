"""本文件模块职责：跨 Java/Python Agent Snapshot 和运行请求数据模型测试。

测试验证字段默认值、枚举、嵌套配置、别名和安全限制，确保配置契约变化能被及时发现。
"""

import pytest
from pydantic import ValidationError

from data_agent_runtime.schemas import (
    AgentSnapshot,
    ModelConfig,
    RunRequest,
    RunResumeRequest,
    UserContext,
)


def test_run_request_accepts_java_snapshot():
    """
    中文说明：
        验证 tests/test_schemas 中“run_request_accepts_java_snapshot”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    request = RunRequest(
        run_id="run-1",
        message="查询车辆数量",
        agent=AgentSnapshot(
            id="analysis",
            version=1,
            system_prompt="你是数据分析助手",
            model=ModelConfig(name="gpt-4o-mini"),
        ),
        user_context=UserContext(
            user_id="u1",
            tenant_id="t1",
        ),
        session_id="session-1",
    )

    assert request.agent.id == "analysis"
    assert request.user_context.tenant_id == "t1"
    assert request.session_id == "session-1"


def test_subagent_uses_full_runtime_configuration():
    """
    中文说明：
        验证 tests/test_schemas 中“subagent_uses_full_runtime_configuration”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    request = RunRequest(
        run_id="run-subagent-1",
        message="分析数据",
        agent=AgentSnapshot(
            id="analysis",
            version=1,
            system_prompt="你是主 Agent",
            model=ModelConfig(name="gpt-4o-mini"),
            subagents=[
                {
                    "name": "metadata-agent",
                    "description": "查询元数据",
                    "model": {"name": "gpt-4o-mini", "temperature": 0.0},
                    "tool_allowlist": ["metadata_search"],
                    "plan": {"enabled": True, "max_steps": 5},
                    "compression": {"trigger_tokens": 12000},
                    "rag": {
                        "enabled": True,
                        "tool_allowlist": ["search_metric_definition"],
                    },
                    "workspace": {"enabled": True, "read_only": True},
                    "max_steps": 8,
                }
            ],
        ),
        user_context=UserContext(user_id="u1", tenant_id="t1"),
    )

    subagent = request.agent.subagents[0]
    assert subagent.model is not None
    assert subagent.model.name == "gpt-4o-mini"
    assert subagent.plan.enabled is True
    assert subagent.rag.enabled is True
    assert subagent.workspace.read_only is True
    assert subagent.max_steps == 8


def test_subagent_supports_nested_full_runtime_configuration():
    """
    中文说明：
        验证 tests/test_schemas 中“subagent_supports_nested_full_runtime_configuration”这一行为，确保协议、状态变化和异常边界符合预期。

    参数：
        - 无：函数使用实例属性、模块配置或闭包变量完成工作。

    返回：
        根据具体分支返回结果或抛出异常。

    异常与边界：
        外部服务、文件系统、队列和模型调用失败时保留原始错误语义，交由上层统一记录、重试或转换。
    """
    request = RunRequest(
        run_id="run-subagent-2",
        message="分析数据",
        agent=AgentSnapshot(
            id="analysis",
            version=1,
            system_prompt="你是主 Agent",
            model=ModelConfig(name="gpt-4o-mini"),
            subagents=[
                {
                    "name": "analysis-agent",
                    "description": "分析数据",
                    "subagents": [
                        {
                            "name": "metadata-agent",
                            "description": "查询元数据",
                            "model_name": "gpt-4o-mini",
                        }
                    ],
                }
            ],
        ),
        user_context=UserContext(user_id="u1", tenant_id="t1"),
    )

    nested = request.agent.subagents[0].subagents[0]
    assert nested.model is not None
    assert nested.model.name == "gpt-4o-mini"


def _optional_snapshot(**overrides):
    """
    中文说明：
        构造带可选能力的 AgentSnapshot，用于验证 interact_on / response_format /
        memory_sources 的校验规则。

    参数：
        - **overrides: 未声明类型：覆盖默认字段。

    返回：
        AgentSnapshot 实例。

    异常与边界：
        非法字段由 Pydantic 抛出 ValidationError。
    """
    values = {
        "id": "agent-optional",
        "version": 1,
        "system_prompt": "你是数据分析助手",
        "model": {"name": "gpt-4o-mini"},
    }
    values.update(overrides)
    return AgentSnapshot(**values)


def test_snapshot_accepts_optional_agent_capabilities():
    """
    中文说明：
        验证快照可以声明工具级确认、结构化输出与记忆文件，并保持原有字段语义。

    参数：
        - 无：函数使用模块内构造函数完成工作。

    返回：
        None。

    异常与边界：
        无外部依赖。
    """
    snapshot = _optional_snapshot(
        interrupt_on={"sandbox_run": True},
        response_format={"type": "object", "properties": {"answer": {"type": "string"}}},
        memory_sources=["/AGENTS.md", "/memory/AGENTS.md"],
    )
    assert snapshot.interrupt_on == {"sandbox_run": True}
    assert snapshot.response_format["type"] == "object"
    assert snapshot.memory_sources == ["/AGENTS.md", "/memory/AGENTS.md"]


def test_snapshot_rejects_non_object_response_format():
    """
    中文说明：
        验证结构化输出的根 schema 必须是 object，避免下游无法按对象解析。

    参数：
        - 无：函数使用模块内构造函数完成工作。

    返回：
        None。

    异常与边界：
        期望抛出 ValidationError。
    """
    with pytest.raises(ValidationError, match="root schema type must be 'object'"):
        _optional_snapshot(response_format={"type": "array"})


def test_snapshot_rejects_memory_path_traversal():
    """
    中文说明：
        验证记忆文件路径必须是工作区绝对路径，禁止路径穿越与反斜杠。

    参数：
        - 无：函数使用模块内构造函数完成工作。

    返回：
        None。

    异常与边界：
        期望抛出 ValidationError。
    """
    with pytest.raises(ValidationError, match="absolute workspace path"):
        _optional_snapshot(memory_sources=["../etc/passwd"])
    with pytest.raises(ValidationError, match="absolute workspace path"):
        _optional_snapshot(memory_sources=["AGENTS.md"])


def test_snapshot_rejects_empty_interrupt_tool_name():
    """
    中文说明：
        验证 interrupt_on 的工具名不能为空，避免配置静默失效。

    参数：
        - 无：函数使用模块内构造函数完成工作。

    返回：
        None。

    异常与边界：
        期望抛出 ValidationError。
    """
    with pytest.raises(ValidationError, match="tool name must not be empty"):
        _optional_snapshot(interrupt_on={" ": True})


def test_run_resume_request_validates_decision_types():
    """
    中文说明：
        验证恢复请求只接受受支持的决策类型，并允许最小合法决策。

    参数：
        - 无：函数使用模块内类型完成工作。

    返回：
        None。

    异常与边界：
        非法类型期望抛出 ValidationError。
    """
    request = RunResumeRequest(decisions=[{"type": "approve"}])
    assert request.decisions == [{"type": "approve"}]
    with pytest.raises(ValidationError, match="decision type must be one of"):
        RunResumeRequest(decisions=[{"type": "exec"}])


def test_snapshot_rejects_blank_rubric():
    """
    中文说明：
        验证声明 rubric 时不能是空白字符串，避免自评中间件拿到无效标准空转。

    参数：
        - 无：函数使用模块内构造函数完成工作。

    返回：
        None。

    异常与边界：
        期望抛出 ValidationError。
    """
    with pytest.raises(ValidationError, match="rubric must not be blank"):
        _optional_snapshot(rubric="   ")


def test_snapshot_rejects_too_long_rubric():
    """
    中文说明：
        验证 rubric 长度上限，避免把超大文本当作评分标准塞进每次模型调用。

    参数：
        - 无：函数使用模块内构造函数完成工作。

    返回：
        None。

    异常与边界：
        期望抛出 ValidationError。
    """
    with pytest.raises(ValidationError):
        _optional_snapshot(rubric="x" * 8001)


def _async_spec(**overrides):
    """
    中文说明：
        构造一个合法的异步子 Agent 声明，便于验证覆盖字段。

    参数：
        - **overrides: 未声明类型：覆盖默认值。

    返回：
        异步子 Agent 声明的字典。

    异常与边界：
        无外部依赖。
    """
    values = {
        "name": "remote-a",
        "description": "远程分析",
        "graph_id": "graph-a",
        "url": "https://agent-protocol.test",
    }
    values.update(overrides)
    return values


def test_snapshot_accepts_async_subagents():
    """
    中文说明：
        验证异步子 Agent 声明可以被快照接受，并保留更新策略默认值。

    参数：
        - 无：函数使用模块内构造函数完成工作。

    返回：
        None。

    异常与边界：
        无外部依赖。
    """
    snapshot = _optional_snapshot(async_subagents=[_async_spec()])
    assert snapshot.async_subagents[0].update_strategy == "interrupt"


def test_snapshot_rejects_relative_async_subagent_url():
    """
    中文说明：
        验证异步子 Agent 必须声明绝对 HTTP(S) 地址，避免出现无法路由的配置。

    参数：
        - 无：函数使用模块内构造函数完成工作。

    返回：
        None。

    异常与边界：
        期望抛出 ValidationError。
    """
    with pytest.raises(ValidationError, match="absolute HTTP"):
        _optional_snapshot(async_subagents=[_async_spec(url="agent-protocol")])


def test_snapshot_rejects_duplicate_async_subagent_names():
    """
    中文说明：
        验证异步子 Agent 名称唯一，避免工具参数歧义。

    参数：
        - 无：函数使用模块内构造函数完成工作。

    返回：
        None。

    异常与边界：
        期望抛出 ValidationError。
    """
    with pytest.raises(ValidationError, match="names must be unique"):
        _optional_snapshot(
            async_subagents=[_async_spec(), _async_spec(graph_id="graph-b")]
        )


def test_todo_tool_defaults_to_disabled():
    """
    中文说明：
        验证规划工具默认关闭，旧快照不会因为升级而多出工具。

    参数：
        - 无：函数使用模块内构造函数完成工作。

    返回：
        None。

    异常与边界：
        无外部依赖。
    """
    snapshot = _optional_snapshot()
    assert snapshot.plan.todo_tool is False
