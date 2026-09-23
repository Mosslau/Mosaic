# exercises/sol-05-fastapi-crud.py —— 练习 5 参考实现：FastAPI 最小 CRUD
# 验证环境：Python 3.13.9，fastapi 0.139.1，pydantic 2.12.4，httpx 0.28.1（TestClient 依赖）
# 运行：python3 sol-05-fastapi-crud.py（TestClient 自测，离线可跑，已验证）
#       或 uvicorn sol-05-fastapi-crud:app --reload 后开 http://127.0.0.1:8000/docs
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Reading API")


class Reading(BaseModel):  # 一个 str 字段 + 一个数值字段
    device_id: str
    speed: float


readings: list[Reading] = []


@app.get("/readings")
def list_readings():
    return readings


@app.post("/readings", status_code=201)
def add_reading(reading: Reading):  # 类型不符自动 422，无需手工检查
    readings.append(reading)
    return reading


if __name__ == "__main__":
    from fastapi.testclient import TestClient

    client = TestClient(app)
    ok = client.post("/readings", json={"device_id": "V001", "speed": 80})
    bad = client.post("/readings", json={"device_id": "V001", "speed": "很快"})
    print("POST 合法:", ok.status_code)  # 201
    print("POST 非法:", bad.status_code)  # 422
    print("GET:", client.get("/readings").json())
