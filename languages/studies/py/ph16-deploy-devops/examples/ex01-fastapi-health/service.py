#!/usr/bin/env python3
"""ex01 的 FastAPI 服务本体：健康检查 + 一个最小的推理端点（ex01-fastapi-health/service.py）。

验证环境：Python 3.13.9（macOS arm64）+ fastapi 0.139.1 + uvicorn 0.50.0（本机已装并实测）
运行（手动）：
    # 1. 在本目录起服务（生产形态，去掉 --reload）
    python3 -m uvicorn service:app --host 127.0.0.1 --port 8016
    # 2. 另一个终端打健康检查端点
    curl http://127.0.0.1:8016/health
自动验证：python3 check_service.py（同一目录，起真实 uvicorn 子进程 + httpx 断言）

端点设计（roadmap 必会概念：服务要有健康检查）：
- GET /health  —— liveness：进程活着就返回 200（负载均衡器据此摘除死进程）
- GET /ready   —— readiness：依赖（这里是模型）就绪才返回 200，未就绪返回 503
- POST /predict —— 最小推理端点：输入工况，返回「规则模型」的预测（教学占位，
  真实模型产物的加载见 ../../project/ 的部署模板）
"""

from __future__ import annotations

from fastapi import FastAPI, Response
from pydantic import BaseModel, Field

app = FastAPI(title="ex01-health-demo", version="0.1.0")

# readiness 探针要检查的「依赖就绪」状态（真实服务里通常是模型已加载/数据库可连）
_state = {"model_ready": True}


class Condition(BaseModel):
    """电池工况输入（与 ph15 电池健康数据的特征一致）。"""

    cycles: float = Field(ge=0, description="累计充放电循环次数")
    avg_temp: float = Field(description="平均工作温度 °C")
    depth: float = Field(ge=0, le=100, description="平均放电深度 %")
    c_rate: float = Field(gt=0, description="平均充电倍率 C")


def rule_based_soh(c: Condition) -> float:
    """规则模型占位：与 ph15 合成数据同一老化公式（无噪声项），SOH 截断到 [40, 100]。"""
    loss = (
        0.008
        + 0.00025 * max(c.avg_temp - 25, 0)
        + 0.0005 * max(c.depth - 70, 0)
        + 0.0015 * max(c.c_rate - 1.5, 0)
    )
    return min(100.0, max(40.0, 100.0 - c.cycles * loss))


@app.get("/health")
def health() -> dict[str, str]:
    """liveness：不做任何依赖检查——进程能响应就算活。"""
    return {"status": "ok"}


@app.get("/ready")
def ready(response: Response) -> dict[str, str]:
    """readiness：依赖未就绪时返回 503，负载均衡器会把流量切走。"""
    if not _state["model_ready"]:
        response.status_code = 503
        return {"status": "not ready"}
    return {"status": "ready"}


@app.post("/admin/fail-model")
def fail_model() -> dict[str, str]:
    """教学用故障注入：翻转模型就绪标志，用来验证 readiness 探针真的在干活。"""
    _state["model_ready"] = not _state["model_ready"]
    return {"model_ready": str(_state["model_ready"])}


@app.post("/predict")
def predict(cond: Condition) -> dict[str, float]:
    """最小推理端点：规则模型预测 SOH。"""
    return {"soh": round(rule_based_soh(cond), 1)}
