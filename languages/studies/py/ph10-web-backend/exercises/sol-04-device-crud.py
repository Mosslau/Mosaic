# exercises/sol-04-device-crud.py —— 练习 4 参考实现：设备管理 API（SQLAlchemy 2.0 + SQLite + response_model）
# 验证环境：Python 3.13.9；fastapi 0.139.1 / sqlalchemy 2.0.43 / pydantic 2.12.4 / httpx 0.28.1
# 运行：python3 sol-04-device-crud.py（离线可跑，TestClient 验证，不起真实服务）
# 验证状态：已验证 —— 实测输出：POST 201（含 id/online）；重复 device_id 409；GET 列表 200；
#           GET 单个 200 / 不存在 404；PUT 200；DELETE 204；数据库文件在临时目录
import tempfile
from collections.abc import Iterator
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DB_PATH = Path(tempfile.mkdtemp(prefix="ph10-sol04-db-")) / "devices.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class Base(DeclarativeBase):
    pass


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(unique=True, index=True)
    model: Mapped[str]
    online: Mapped[bool] = mapped_column(default=False)


Base.metadata.create_all(engine)          # 演示建表；正式项目用 Alembic 迁移（主文档 3.7）


class DeviceIn(BaseModel):                 # 输入模型
    device_id: str = Field(min_length=17, max_length=17)
    model: str


class DeviceOut(DeviceIn):                 # 输出契约：含 id/online，不含内部字段
    id: int
    online: bool
    model_config = {"from_attributes": True}   # 允许从 ORM 对象序列化


app = FastAPI(title="设备管理 API")


def get_session() -> Iterator[Session]:      # 依赖注入：每请求一个 Session，用完自动关
    with Session(engine) as session:       # 防连接池泄漏（主文档 4.4）
        yield session


@app.post("/devices", status_code=201, response_model=DeviceOut)
def create_device(body: DeviceIn, session: Session = Depends(get_session)):
    device = Device(device_id=body.device_id, model=body.model)
    session.add(device)
    try:
        session.commit()
    except IntegrityError:                 # 唯一约束冲突（device_id 重复）
        raise HTTPException(status_code=409, detail="device_id 已存在")
    session.refresh(device)
    return device


@app.get("/devices", response_model=list[DeviceOut])
def list_devices(session: Session = Depends(get_session)):
    return session.scalars(select(Device)).all()


@app.get("/devices/{device_id}", response_model=DeviceOut)
def get_device(device_id: int, session: Session = Depends(get_session)):
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    return device


@app.put("/devices/{device_id}", response_model=DeviceOut)
def update_device(device_id: int, body: DeviceIn, session: Session = Depends(get_session)):
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    device.device_id, device.model = body.device_id, body.model
    session.commit()
    return device


@app.delete("/devices/{device_id}", status_code=204)
def delete_device(device_id: int, session: Session = Depends(get_session)):
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    session.delete(device)
    session.commit()


def main() -> None:
    print("数据库文件:", DB_PATH)
    device_id = "LVGBE40K5GG123456"            # 17 位 DEVICE_ID
    with TestClient(app) as client:
        r = client.post("/devices", json={"device_id": device_id, "model": "EV-A"})
        print("POST /devices        ->", r.status_code, r.json())
        r = client.post("/devices", json={"device_id": device_id, "model": "EV-B"})
        print("重复 device_id             ->", r.status_code, r.json())

        r = client.get("/devices")
        print("GET /devices         ->", r.status_code, "条数:", len(r.json()))

        r = client.get("/devices/1")
        print("GET /devices/1       ->", r.status_code, r.json())
        r = client.get("/devices/999")
        print("GET /devices/999     ->", r.status_code, r.json())

        r = client.put("/devices/1", json={"device_id": device_id, "model": "EV-C"})
        print("PUT /devices/1       ->", r.status_code, r.json())

        r = client.delete("/devices/1")
        print("DELETE /devices/1    ->", r.status_code, r.text)


if __name__ == "__main__":
    main()
