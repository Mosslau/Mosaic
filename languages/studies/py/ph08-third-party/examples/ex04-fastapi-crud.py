# examples/ex04-fastapi-crud.py —— 主文档 6.4：FastAPI 接口（Pydantic 模型 + CRUD 路由）
# 验证环境：Python 3.13.9，fastapi 0.139.1，pydantic 2.12.4，httpx 0.28.1（TestClient 依赖）
# 运行：python3 ex04-fastapi-crud.py（TestClient 自测，离线可跑，已验证）
#       或 uvicorn ex04-fastapi-crud:app --reload --port 8000 后浏览器开 http://127.0.0.1:8000/docs
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Car API")


class Car(BaseModel):  # Pydantic：声明 + 校验 + 文档三合一
    vehicle_id: str
    speed: float


cars: list[Car] = []


@app.get("/cars")
def list_cars():
    return cars


@app.get("/cars/{idx}")
def get_car(idx: int):
    if idx >= len(cars):
        raise HTTPException(status_code=404, detail="not found")
    return cars[idx]


@app.post("/cars", status_code=201)
def add_car(car: Car):  # 请求体自动校验，类型不符返回 422
    cars.append(car)
    return car


@app.put("/cars/{idx}")
def update_car(idx: int, car: Car):
    cars[idx] = car
    return car


@app.delete("/cars/{idx}")
def delete_car(idx: int):
    return cars.pop(idx)


if __name__ == "__main__":  # 免启动服务，用 TestClient 自测
    from fastapi.testclient import TestClient

    client = TestClient(app)
    print("GET 空列表:", client.get("/cars/0").status_code)  # 404：越界守卫
    print(
        "POST 合法:",
        client.post("/cars", json={"vehicle_id": "V001", "speed": 80}).status_code,
    )  # 201
    print(
        "POST 非法:",
        client.post("/cars", json={"vehicle_id": "V001", "speed": "很快"}).status_code,
    )  # 422
    print("GET:", client.get("/cars").json())
    print("DELETE:", client.delete("/cars/0").status_code)  # 200
