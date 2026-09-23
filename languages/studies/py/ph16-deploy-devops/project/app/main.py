"""FastAPI 部署模板的服务入口（ph16 project/app/main.py）。

端点：GET /health（liveness）、GET /ready（readiness）、POST /predict（推理）、
GET /metrics（Prometheus 文本）。依赖加载放 lifespan：进程起来 ≠ 就绪，
就绪由 /ready 如实报告（MODEL_PATH 配了但产物缺失 → 503，不静默降级）。

启动（生产形态）：
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
配置（环境变量，12-factor）：
    MODEL_PATH=/models/model.joblib   # 不设置则用规则兜底模型
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel, Field

from app.metrics import MetricsRegistry
from app.predictor import FEATURES, Predictor, load_predictor


class Condition(BaseModel):
    """部件工况输入（特征顺序与 train.py 训练时一致）。"""

    cycles: float = Field(ge=0, description="累计充放电循环次数")
    avg_temp: float = Field(description="平均工作温度 °C")
    depth: float = Field(ge=0, le=100, description="平均放电深度 %")
    c_rate: float = Field(gt=0, description="平均充电倍率 C")

    def features(self) -> list[float]:
        return [self.cycles, self.avg_temp, self.depth, self.c_rate]


def create_app() -> FastAPI:
    """应用工厂：测试与生产都走这里（测试可注入自己的环境变量后再建 app）。"""
    metrics = MetricsRegistry()
    state: dict[str, Predictor | None] = {"predictor": None}

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        state["predictor"] = load_predictor()  # None = 配置了的产物缺失
        metrics.model_type = (
            state["predictor"].model_type if state["predictor"] is not None else "missing"
        )
        yield
        state["predictor"] = None

    app = FastAPI(title="health-api", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def count_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        metrics.record_request(request.url.path, response.status_code)
        return response

    @app.get("/health")
    def health() -> dict[str, str]:
        """liveness：进程活着即 200。"""
        return {"status": "ok"}

    @app.get("/ready")
    def ready(response: Response) -> dict[str, str]:
        """readiness：推理后端可用才 200；配置了产物但缺失时 503。"""
        if state["predictor"] is None:
            response.status_code = 503
            return {"status": "not ready", "reason": "MODEL_PATH 配置的产物缺失"}
        return {"status": "ready", "model_type": state["predictor"].model_type}

    @app.post("/predict")
    def predict(cond: Condition, response: Response) -> dict[str, object]:
        """HEALTH 推理；未就绪时 503（宁缺毋滥，不拿没加载好的模型骗人）。"""
        predictor = state["predictor"]
        if predictor is None:
            response.status_code = 503
            return {"error": "model not ready"}
        t0 = time.perf_counter()
        health = predictor.predict_health(cond.features())
        metrics.record_predict(time.perf_counter() - t0)
        return {
            "health": round(health, 1),
            "grade": "健康" if health >= 90 else ("退化" if health >= 80 else "临界"),
            "model_type": predictor.model_type,
            "features": FEATURES,
        }

    @app.get("/metrics")
    def metrics_endpoint() -> Response:
        return Response(metrics.render(), media_type="text/plain; version=0.0.4")

    return app


app = create_app()
