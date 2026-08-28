from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import health, metrics

app = FastAPI(
    title="OceanVerse Analysis Service",
    description="车辆数据分析服务",
    version="0.1.0",
)

# 注册路由
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["metrics"])

# Prometheus 指标
Instrumentator().instrument(app).expose(app)


@app.on_event("startup")
async def startup():
    pass


@app.on_event("shutdown")
async def shutdown():
    pass
