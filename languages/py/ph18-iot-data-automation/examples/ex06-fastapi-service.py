#!/usr/bin/env python3
# examples/ex06-fastapi-service.py —— 遥测数据服务（主文档 3.6）
# 验证环境（目标）：Python 3.13 + fastapi + uvicorn + httpx（TestClient 依赖 httpx）
# 运行（自检）：python3 ex06-fastapi-service.py
# 运行（服务）：python3 ex06-fastapi-service.py --serve（监听 127.0.0.1:8000）
# 测试：python3 -m pytest ex06-fastapi-service.py -q
# lint：ruff check ex06-fastapi-service.py
# 验证状态：已验证（Python 3.13.12 + fastapi + httpx 本机实测：TestClient 自检与 pytest 全绿）
"""把清洗/分析流水线包成 FastAPI 数据服务：车队查询 + 时间序列 + 规则事件 + 遥测上报。

ph10 讲了路由/请求校验/文档，ph16 讲了 uvicorn 部署——这里示范的是**数据服务层**的
组织方式：pandas 清洗分析负责算、pydantic 在 API 边界做 fail-fast 校验、服务只做编排。
供教学的最小样例，生产数据源应是 parquet/DB/消息队列（ph11/ph16 的栈）。
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

# ---- 数据层：造样例 + 缓存（真实工程里替换为 parquet/DB/消息队列）----

VEHICLES = ("V001", "V002", "V003")


def generate_sample(seconds: int = 600, seed: int = 8) -> pd.DataFrame:
    """自造车队样例遥测并落盘 /tmp（服务启动时加载进内存缓存）。"""
    rng = np.random.default_rng(seed)
    t = np.arange(seconds, dtype=float)
    frames: list[pd.DataFrame] = []
    for vehicle_id in VEHICLES:
        temp = 30 + rng.normal(0, 0.5, seconds)
        if vehicle_id == "V002":  # 给 V002 埋一段持续高温，供 /events 演示
            temp[300:330] = 60.0
        frames.append(
            pd.DataFrame(
                {
                    "ts": t + 1_700_000_000,
                    "vehicle_id": vehicle_id,
                    "speed_kmh": 50
                    + 20 * np.sin(t / 60 + rng.random())
                    + rng.normal(0, 0.5, seconds),
                    "soc_pct": np.clip(90 - t / 60 + rng.normal(0, 0.1, seconds), 0, 100),
                    "pack_voltage_v": 385 + rng.normal(0, 0.6, seconds),
                    "pack_temp_c": temp,
                    "pack_current_a": -25 + rng.normal(0, 1.5, seconds),
                    "power_kw": -9.6 + rng.normal(0, 0.8, seconds),
                }
            )
        )
    df = pd.concat(frames, ignore_index=True)
    return df


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时加载样例数据到 app.state，关闭时清理。"""
    out_dir = Path("/tmp/ph18-ex06")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "sample_telemetry.csv"
    generate_sample().to_csv(csv_path, index=False)
    df = pd.read_csv(csv_path)
    app.state.df = df
    app.state.ingested: dict[str, int] = {}
    yield
    app.state.df = pd.DataFrame()  # 释放缓存（演示用；生产应显式关连接池）


app = FastAPI(
    title="Telemetry Data Service",
    description="车辆遥测数据服务（ph18 教学示例）",
    lifespan=lifespan,
)

SERIES_FIELDS: tuple[str, ...] = (
    "speed_kmh",
    "soc_pct",
    "pack_voltage_v",
    "pack_temp_c",
    "pack_current_a",
    "power_kw",
)

# ---- API 边界模型：pydantic 校验发生在进入业务逻辑之前（ph10 的边界哲学）----


class TelemetryPoint(BaseModel):
    ts: float = Field(ge=1_500_000_000, le=2_000_000_000, description="Unix 秒")
    vehicle_id: str = Field(pattern=r"^V\d{3}$")
    speed_kmh: float = Field(ge=0, le=220)
    soc_pct: float = Field(ge=0, le=100)
    pack_voltage_v: float = Field(ge=250, le=420)
    pack_temp_c: float = Field(ge=-40, le=65)
    pack_current_a: float = Field(ge=-300, le=400)
    power_kw: float = Field(ge=-300, le=300)


class SeriesPoint(BaseModel):
    ts: float
    value: float


class Summary(BaseModel):
    vehicle_id: str
    points: int
    mean_speed: float
    mean_pack_temp: float
    mean_power_kw: float
    min_soc: float
    max_soc: float


class FaultEvent(BaseModel):
    ts_start: float
    ts_end: float
    detail: str


class IngestAck(BaseModel):
    vehicle_id: str
    accepted: int


# ---- 路由：薄编排层，业务逻辑保持在 pandas 函数里（可单独单测）----


def _vehicle_df(app: FastAPI, vehicle_id: str) -> pd.DataFrame:
    df: pd.DataFrame = app.state.df
    part = df[df["vehicle_id"] == vehicle_id]
    if part.empty:
        raise HTTPException(status_code=404, detail=f"车辆 {vehicle_id} 不在车队中")
    return part.sort_values("ts")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/vehicles", response_model=list[str])
def list_vehicles() -> list[str]:
    return sorted(VEHICLES)


@app.get("/vehicles/{vehicle_id}/summary", response_model=Summary)
def vehicle_summary(vehicle_id: str) -> Summary:
    part = _vehicle_df(app, vehicle_id)
    return Summary(
        vehicle_id=vehicle_id,
        points=len(part),
        mean_speed=float(part["speed_kmh"].mean()),
        mean_pack_temp=float(part["pack_temp_c"].mean()),
        mean_power_kw=float(part["power_kw"].mean()),
        min_soc=float(part["soc_pct"].min()),
        max_soc=float(part["soc_pct"].max()),
    )


@app.get("/vehicles/{vehicle_id}/series", response_model=list[SeriesPoint])
def vehicle_series(
    vehicle_id: str,
    field: Literal[
        "speed_kmh", "soc_pct", "pack_voltage_v", "pack_temp_c", "pack_current_a", "power_kw"
    ],
    from_ts: float | None = Query(default=None, description="起始 Unix 秒"),
    to_ts: float | None = Query(default=None, description="结束 Unix 秒"),
    limit: int = Query(default=2000, ge=1, le=100_000),
) -> list[SeriesPoint]:
    part = _vehicle_df(app, vehicle_id)
    if from_ts is not None:
        part = part[part["ts"] >= from_ts]
    if to_ts is not None:
        part = part[part["ts"] <= to_ts]
    part = part.tail(limit)
    return [
        SeriesPoint(ts=float(ts), value=float(v))
        for ts, v in zip(part["ts"], part[field], strict=False)
    ]


@app.get("/vehicles/{vehicle_id}/events", response_model=list[FaultEvent])
def vehicle_events(vehicle_id: str) -> list[FaultEvent]:
    """规则事件（极简版）：温度超过 55℃ 的持续段 → 过热事件（ex04 的规则引擎子集）。"""
    part = _vehicle_df(app, vehicle_id)
    hot = (part["pack_temp_c"] > 55.0).to_numpy()
    events: list[FaultEvent] = []
    start: int | None = None
    for i, is_hot in enumerate(hot.tolist()):
        if is_hot and start is None:
            start = i
        elif not is_hot and start is not None:
            events.append(
                FaultEvent(
                    ts_start=float(part["ts"].iloc[start]),
                    ts_end=float(part["ts"].iloc[i - 1]),
                    detail="pack_temp_c > 55℃",
                )
            )
            start = None
    if start is not None:
        events.append(
            FaultEvent(
                ts_start=float(part["ts"].iloc[start]),
                ts_end=float(part["ts"].iloc[-1]),
                detail="pack_temp_c > 55℃",
            )
        )
    return events


@app.post("/vehicles/{vehicle_id}/telemetry", response_model=IngestAck)
def ingest_telemetry(vehicle_id: str, point: TelemetryPoint) -> IngestAck:
    """上报单点遥测：pydantic 已做量程/格式校验；这里只记账（演示）。"""
    app.state.ingested[vehicle_id] = app.state.ingested.get(vehicle_id, 0) + 1
    return IngestAck(vehicle_id=vehicle_id, accepted=app.state.ingested[vehicle_id])


def main_demo() -> None:
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        vehicles = client.get("/vehicles").json()
        assert vehicles == ["V001", "V002", "V003"]
        summary = client.get("/vehicles/V001/summary").json()
        print("V001 summary:", summary)
        assert summary["vehicle_id"] == "V001" and summary["points"] == 600

        series = client.get(
            "/vehicles/V001/series", params={"field": "soc_pct", "limit": 10}
        ).json()
        print("V001 soc 最后 10 点:", [round(p["value"], 1) for p in series])
        assert len(series) == 10

        events = client.get("/vehicles/V002/events").json()
        print("V002 过热事件:", events)
        assert events and events[0]["detail"] == "pack_temp_c > 55℃"
        assert client.get("/vehicles/V001/events").json() == []

        ack = client.post(
            "/vehicles/V001/telemetry",
            json={
                "ts": 1_700_000_001,
                "vehicle_id": "V001",
                "speed_kmh": 60,
                "soc_pct": 88,
                "pack_voltage_v": 386,
                "pack_temp_c": 31,
                "pack_current_a": -30,
                "power_kw": -11.5,
            },
        ).json()
        assert ack == {"vehicle_id": "V001", "accepted": 1}
        # 越界值必须被 pydantic 拦在业务外（fail-fast，返回 422）
        bad = client.post(
            "/vehicles/V001/telemetry",
            json={**ack, "speed_kmh": 500.0, "power_kw": 0},
        )
        assert bad.status_code == 422
        assert client.get("/vehicles/NOPE/summary").status_code == 404
        print("\n自检通过：健康检查/摘要/时序/事件/上报/422/404 全绿")


def test_health() -> None:
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


def test_summary_and_series() -> None:
    with TestClient(app) as client:
        summary = client.get("/vehicles/V002/summary").json()
        assert summary["points"] == 600
        series = client.get(
            "/vehicles/V001/series",
            params={"field": "speed_kmh", "from_ts": 1_700_000_100, "to_ts": 1_700_000_110},
        ).json()
        assert len(series) == 11  # 闭区间 100..110
        assert all(1_700_000_100 <= p["ts"] <= 1_700_000_110 for p in series)


def test_events_only_on_hot_vehicle() -> None:
    with TestClient(app) as client:
        v001 = client.get("/vehicles/V001/events").json()
        v002 = client.get("/vehicles/V002/events").json()
        assert v001 == []
        assert len(v002) == 1 and v002[0]["ts_end"] - v002[0]["ts_start"] >= 29


def test_invalid_payload_rejected_and_404() -> None:
    with TestClient(app) as client:
        assert client.post("/vehicles/V001/telemetry", json={}).status_code == 422
        assert client.get("/vehicles/V999/summary").status_code == 404


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        import uvicorn

        uvicorn.run(app, host="127.0.0.1", port=8000)
    else:
        main_demo()
