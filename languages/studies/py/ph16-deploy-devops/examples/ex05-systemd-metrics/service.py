#!/usr/bin/env python3
"""ex05 的监控版 FastAPI 服务：/metrics Prometheus 端点（ex05-systemd-metrics/service.py）。

验证环境：Python 3.13.9（macOS arm64）+ fastapi 0.139.1 + uvicorn 0.50.0（本机已装并实测）
运行（手动）：
    # 1. 起服务
    python3 -m uvicorn service:app --host 127.0.0.1 --port 8017
    # 2. 打几个请求后看指标端点
    curl http://127.0.0.1:8017/metrics
自动验证：python3 check_metrics.py（同目录，起真实 uvicorn 子进程 + httpx 断言）

指标设计（主文档 3.7）：不引第三方库，手写最小 Prometheus 文本格式——
Counter（请求总数，单调递增）/ Histogram（预测耗时，count+sum 两列即可算平均值）/
Gauge（瞬时状态）。真实生产用 prometheus_client 库，格式完全一致。
"""

from __future__ import annotations

import time

from fastapi import FastAPI, Response
from pydantic import BaseModel, Field

app = FastAPI(title="ex05-metrics-demo", version="0.1.0")

# 进程内指标注册表（多进程部署时每进程一份，Prometheus 按实例抓取后聚合——见主文档 4.2）
_counters: dict[str, int] = {}
_hist = {"count": 0, "sum": 0.0}  # predict 耗时：样本数 + 总秒数
_started_at = time.monotonic()


class Condition(BaseModel):
    """电池工况输入（与 ex01 相同）。"""

    cycles: float = Field(ge=0)
    avg_temp: float = Field()
    depth: float = Field(ge=0, le=100)
    c_rate: float = Field(gt=0)


def _bump(name: str) -> None:
    _counters[name] = _counters.get(name, 0) + 1


@app.get("/health")
def health() -> dict[str, str]:
    _bump("health")
    return {"status": "ok"}


@app.post("/predict")
def predict(cond: Condition) -> dict[str, float]:
    """规则模型占位（与 ex01 同一老化公式），顺手记录耗时直方图。"""
    t0 = time.perf_counter()
    loss = (
        0.008
        + 0.00025 * max(cond.avg_temp - 25, 0)
        + 0.0005 * max(cond.depth - 70, 0)
        + 0.0015 * max(cond.c_rate - 1.5, 0)
    )
    soh = min(100.0, max(40.0, 100.0 - cond.cycles * loss))
    _bump("predict")
    _hist["count"] += 1
    _hist["sum"] += time.perf_counter() - t0
    return {"soh": round(soh, 1)}


@app.get("/metrics")
def metrics() -> Response:
    """Prometheus 文本暴露格式（text/plain; version=0.0.4）的最小可用实现。"""
    uptime = time.monotonic() - _started_at
    lines = [
        "# HELP demo_requests_total 各端点请求总数（Counter，单调递增）",
        "# TYPE demo_requests_total counter",
    ]
    for endpoint, count in sorted(_counters.items()):
        lines.append(f'demo_requests_total{{endpoint="{endpoint}"}} {count}')
    lines += [
        "# HELP demo_predict_seconds 预测耗时（Histogram 的 count/sum，平均 = sum/count）",
        "# TYPE demo_predict_seconds histogram",
        f"demo_predict_seconds_count {_hist['count']}",
        f"demo_predict_seconds_sum {_hist['sum']:.6f}",
        "# HELP demo_uptime_seconds 进程运行秒数（Gauge，可升可降的瞬时值）",
        "# TYPE demo_uptime_seconds gauge",
        f"demo_uptime_seconds {uptime:.1f}",
        "",
    ]
    return Response("\n".join(lines), media_type="text/plain; version=0.0.4")
