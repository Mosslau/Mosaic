#!/usr/bin/env python3
# exercises/sol-01-deploy-fastapi.py —— 练习 1 参考实现：可部署的 FastAPI 服务（健康检查双探针）
# 验证环境：Python 3.13.9（macOS arm64）+ fastapi 0.139.1 + httpx 0.28.1（本机已装并实测）
# 运行：python3 sol-01-deploy-fastapi.py（离线可跑，TestClient 进程内验证，已验证）
# 生产启动：python3 -m uvicorn sol-01-deploy-fastapi:app --host 0.0.0.0 --port 8000
#   （文件名含连字符不能 import，仅示意——真实项目用包路径，如 project/ 的 app.main:app）
# 验证状态：已验证 —— TestClient 实测 /health 200、/ready 200（依赖断开后 503）、
#           /predict 输入校验 422、正常预测 health=80.5
"""练习 1 参考实现：写一个「能上线」的 FastAPI 服务。

与玩具 demo 的差别就在三件事（对应题目验收标准）：
1. 双探针健康检查：/health（liveness）与 /ready（readiness）分工明确；
2. 输入校验交给 Pydantic（非法输入自动 422，不进业务逻辑）；
3. 生命周期钩子管理依赖（模型加载放 lifespan，失败则 readiness 变 503）。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field


class Condition(BaseModel):
    """部件工况（与主文档/ph15 的特征口径一致）。"""

    cycles: float = Field(ge=0)
    avg_temp: float = Field()
    depth: float = Field(ge=0, le=100)
    c_rate: float = Field(gt=0)


class State:
    """服务级状态：模型是否就绪（真实项目里是 joblib 产物，见 project/）。"""

    model_ready: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """启动时加载依赖（这里是模拟加载模型），关停时释放。"""
    State.model_ready = True  # 真实代码：joblib.load(...)；失败就保持 False
    yield
    State.model_ready = False


app = FastAPI(title="sol-01-deployable-service", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    """liveness：进程活着即 200——挂了由守护进程（systemd/compose）拉起。"""
    return {"status": "ok"}


@app.get("/ready")
def ready(response: Response) -> dict[str, str]:
    """readiness：模型没加载完不接收流量（503），加载完才进负载均衡池。"""
    if not State.model_ready:
        response.status_code = 503
        return {"status": "not ready"}
    return {"status": "ready"}


@app.post("/predict")
def predict(cond: Condition) -> dict[str, float]:
    """规则模型占位：HEALTH = 100 − cycles × 分段老化率（与 ex01 同公式）。"""
    loss = (
        0.008
        + 0.00025 * max(cond.avg_temp - 25, 0)
        + 0.0005 * max(cond.depth - 70, 0)
        + 0.0015 * max(cond.c_rate - 1.5, 0)
    )
    return {"health": round(min(100.0, max(40.0, 100.0 - cond.cycles * loss)), 1)}


def main() -> None:
    """TestClient 进程内验证（真实 uvicorn 起服务的验证见 examples/ex01）。"""
    with TestClient(app) as client:  # with 触发 lifespan（模拟「启动加载模型」）
        r = client.get("/health")
        assert r.status_code == 200 and r.json() == {"status": "ok"}
        print(f"GET /health  -> {r.status_code} {r.json()}")

        r = client.get("/ready")
        assert r.status_code == 200 and r.json() == {"status": "ready"}
        print(f"GET /ready   -> {r.status_code} {r.json()}")

        cond = {"cycles": 1500, "avg_temp": 25, "depth": 80, "c_rate": 1.0}
        r = client.post("/predict", json=cond)
        assert r.status_code == 200 and r.json() == {"health": 80.5}
        print(f"POST /predict -> {r.status_code} {r.json()}")

        # 输入校验：cycles 为负 → 422（校验失败，业务逻辑根本没被调用）
        r = client.post("/predict", json={**cond, "cycles": -1})
        assert r.status_code == 422
        print(f"POST /predict（cycles=-1）-> {r.status_code}（Pydantic 校验拦截）")

        # readiness 分工：模型「挂了」→ /ready 503 而 /health 仍 200
        State.model_ready = False
        r = client.get("/ready")
        assert r.status_code == 503
        r = client.get("/health")
        assert r.status_code == 200
        print("依赖故障时    -> /ready 503、/health 200（探针分工正确）")
    print("sol-01 自检通过")


if __name__ == "__main__":
    main()
