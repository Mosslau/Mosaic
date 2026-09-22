# project/telemetry_api.py —— 设备数据上报 API（ph10 阶段项目）
# 功能：车辆遥测上报（单条 + 批量）、按设备/时间查询、分组统计、日志中间件、统一错误处理。
# 验证环境：Python 3.13.9；fastapi 0.139.1 / sqlalchemy 2.0.43 / pydantic 2.12.4 / uvicorn 0.50.0
# 运行：python3 telemetry_api.py --demo   （离线演示链路，数据库/产物一律在系统临时目录）
#       uvicorn telemetry_api:app --port 8765  （可选：起真实服务，测试优先用 TestClient）
# 测试：pytest -q（在 project/ 目录下）
"""设备数据上报 API。

对应 roadmap（python.md）ph10「推荐项目」第二个「设备数据上报 API」：车辆遥测上报接口
`POST /telemetry`（请求体校验：速度 0~200、SOC 0~100），按设备/时间查询与统计
（结合 ph09 分组统计思维），支持批量写库，日志中间件记录每条上报的耗时与状态码。
"""
import argparse
import logging
import sys
import tempfile
import time
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import uvicorn  # serve 模式使用；demo/测试不依赖
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("telemetry_api")

DEFAULT_MAX_BATCH = 1000


class Base(DeclarativeBase):
    pass


class Telemetry(Base):
    """遥测记录表：一次上报 = 一条记录。"""

    __tablename__ = "telemetry"
    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(index=True)
    ts: Mapped[datetime] = mapped_column(index=True)
    speed: Mapped[float]
    soc: Mapped[float]


class TelemetryIn(BaseModel):
    """上报输入模型：速度 0~200、SOC 0~100（roadmap 要求），ts 为 ISO 8601 字符串。"""

    vehicle_id: str = Field(min_length=1, max_length=32)
    ts: datetime
    speed: float = Field(ge=0, le=200, description="速度 km/h")
    soc: float = Field(ge=0, le=100, description="电量 %")


class TelemetryOut(TelemetryIn):
    id: int
    model_config = {"from_attributes": True}   # 允许从 ORM 对象序列化（主文档 3.5）


def create_app(database_url: str | None = None) -> FastAPI:
    """应用工厂：传入 sqlite 地址构建独立应用；不传则用系统临时目录（产物纪律）。"""
    if database_url is None:
        db_path = Path(tempfile.mkdtemp(prefix="ph10-telemetry-db-")) / "telemetry.db"
        database_url = f"sqlite:///{db_path}"
        logger.info("数据库（临时目录）: %s", db_path)

    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)          # 演示建表；正式项目用 Alembic 迁移（主文档 3.7）

    app = FastAPI(title="设备数据上报 API", version="1.0.0")

    @app.middleware("http")                   # 日志中间件：记录每条上报的耗时与状态码
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        logger.info(
            "%s %s -> %s (%.1f ms)",
            request.method, request.url.path, response.status_code,
            (time.perf_counter() - start) * 1000,
        )
        return response

    def get_session() -> Iterator[Session]:   # 依赖注入：每请求一个 Session，用完自动关
        with Session(engine) as session:      # 防连接池泄漏（主文档 4.4）
            yield session

    @app.post("/telemetry", status_code=201, response_model=TelemetryOut)
    def report(body: TelemetryIn, session: Session = Depends(get_session)):
        """单条上报：校验通过即落库，返回带 id 的完整记录。"""
        row = Telemetry(vehicle_id=body.vehicle_id, ts=body.ts,
                        speed=body.speed, soc=body.soc)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row

    @app.post("/telemetry/batch", status_code=201)
    def report_batch(body: list[TelemetryIn], session: Session = Depends(get_session)):
        """批量上报：任意一条校验失败整体 422（pydantic 结构化错误）；成功后返回条数。"""
        if not 1 <= len(body) <= DEFAULT_MAX_BATCH:
            raise HTTPException(status_code=400,
                                detail=f"批量条数需在 1~{DEFAULT_MAX_BATCH} 之间")
        for item in body:
            session.add(Telemetry(vehicle_id=item.vehicle_id, ts=item.ts,
                                  speed=item.speed, soc=item.soc))
        session.commit()
        return {"inserted": len(body)}

    @app.get("/telemetry", response_model=list[TelemetryOut])
    def list_telemetry(vehicle_id: str | None = None,
                       since: datetime | None = None,
                       until: datetime | None = None,
                       limit: int = Query(100, ge=1, le=1000),
                       session: Session = Depends(get_session)):
        """按设备/时间查询：可选 vehicle_id、since/until（ISO 8601），按时间升序。"""
        stmt = select(Telemetry)
        if vehicle_id:
            stmt = stmt.where(Telemetry.vehicle_id == vehicle_id)
        if since:
            stmt = stmt.where(Telemetry.ts >= since)
        if until:
            stmt = stmt.where(Telemetry.ts <= until)
        stmt = stmt.order_by(Telemetry.ts).limit(limit)
        return session.scalars(stmt).all()

    @app.get("/telemetry/stats")
    def telemetry_stats(vehicle_id: str | None = None,
                        since: datetime | None = None,
                        until: datetime | None = None,
                        session: Session = Depends(get_session)):
        """分组统计（呼应 ph09 分组统计思维）：不传 vehicle_id 按车辆分组，
        传了则只统计该车。返回 count / avg_speed / max_speed / avg_soc。"""
        stmt = select(
            Telemetry.vehicle_id,
            func.count(Telemetry.id).label("count"),
            func.avg(Telemetry.speed).label("avg_speed"),
            func.max(Telemetry.speed).label("max_speed"),
            func.avg(Telemetry.soc).label("avg_soc"),
        )
        if vehicle_id:
            stmt = stmt.where(Telemetry.vehicle_id == vehicle_id)
        if since:
            stmt = stmt.where(Telemetry.ts >= since)
        if until:
            stmt = stmt.where(Telemetry.ts <= until)
        stmt = stmt.group_by(Telemetry.vehicle_id).order_by(Telemetry.vehicle_id)
        return [
            {
                "vehicle_id": r.vehicle_id,
                "count": r.count,
                "avg_speed": round(r.avg_speed, 2),
                "max_speed": round(r.max_speed, 2),
                "avg_soc": round(r.avg_soc, 2),
            }
            for r in session.execute(stmt).all()
        ]

    return app


def build_demo_rows() -> list[TelemetryIn]:
    """构造 3 车 × 24 条确定性模拟遥测（速度 55~85、SOC 88 递减），供 --demo 离线演示。"""
    rows: list[TelemetryIn] = []
    for i, vid in enumerate(["V001", "V002", "V003"]):
        for k in range(24):
            ts = datetime(2024, 6, 1, 8, 0) + timedelta(minutes=30 * k)   # 每 30 秒一条
            rows.append(TelemetryIn(
                vehicle_id=vid,
                ts=ts,
                speed=round(55 + (i * 7) + (k % 5) * 3, 2),
                soc=round(88.0 - k * 0.2, 1),
            ))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="设备数据上报 API：离线演示 / 服务启动")
    parser.add_argument("--demo", action="store_true",
                        help="离线演示：临时库跑通 上报→查询→统计 全链路并自检")
    args = parser.parse_args(argv)

    if not args.demo:
        uvicorn.run("telemetry_api:app", host="127.0.0.1", port=8765)
        return 0

    # 离线演示：TestClient 进程内驱动，不起真实服务、不占端口
    from fastapi.testclient import TestClient

    app = create_app()
    rows = build_demo_rows()
    with TestClient(app) as client:
        r = client.post("/telemetry/batch", json=[row.model_dump(mode="json") for row in rows])
        print("批量上报 ->", r.status_code, r.json(), "（3 车 × 24 条 = 72 条）")

        r = client.post("/telemetry",
                        json={"vehicle_id": "V999", "ts": "2024-06-01T09:00:00",
                              "speed": 250, "soc": 80})   # 速度超限 → 422
        print("非法上报（speed=250）->", r.status_code,
              r.json()["detail"][0]["loc"], r.json()["detail"][0]["type"])

        r = client.get("/telemetry?vehicle_id=V001&limit=3")
        print("按车查询 V001 前 3 条 ->", r.status_code, "条数:", len(r.json()),
              "首条 speed:", r.json()[0]["speed"])

        r = client.get("/telemetry/stats")
        print("全量分组统计:")
        for item in r.json():
            print("  ", item)

        r = client.get("/telemetry/stats?vehicle_id=V001")
        print("单车统计 V001      ->", r.json())

    assert r.status_code == 200 and r.json()[0]["count"] == 24
    print("\n自检通过：批量 72 条入库、非法上报 422、查询与统计结果正确")
    return 0


if __name__ == "__main__":
    sys.exit(main())
