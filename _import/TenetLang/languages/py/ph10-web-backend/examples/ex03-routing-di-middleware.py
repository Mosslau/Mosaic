# examples/ex03-routing-di-middleware.py —— FastAPI 路由 + 依赖注入 + 中间件（TestClient 离线验证）
# 验证环境：Python 3.13.9，fastapi 0.139.1 / starlette 0.49.3 / httpx 0.28.1
# 运行：python3 ex03-routing-di-middleware.py（离线可跑，已验证，不起真实服务）
# 说明：用 fastapi.testclient.TestClient 在进程内驱动应用——不占端口、不留进程，
#       输出/状态码/响应体均为本机实测。覆盖主文档 3.2（路由与 Depends）、
#       3.4（路径/查询参数）、3.8（中间件）、4.3（依赖解析缓存）。
import time
from collections.abc import Awaitable, Callable

from fastapi import Depends, FastAPI, Request
from fastapi.responses import Response
from fastapi.testclient import TestClient

app = FastAPI(title="路由/依赖/中间件 Demo")

# 依赖调用计数：验证「同一请求内同名依赖只解析一次」（主文档 4.3 的请求级缓存）
_dep_calls = 0


def count_calls() -> dict:
    global _dep_calls
    _dep_calls += 1
    return {"calls": _dep_calls}


def require_token() -> dict:                       # 一级依赖：普通函数即可
    return {"user": "demo", "role": "admin"}


def require_admin(user: dict = Depends(require_token)) -> dict:   # 二级依赖：依赖别的依赖
    if user["role"] != "admin":
        raise PermissionError("need admin")        # 简化：完整版用 HTTPException（主文档 3.9）
    return user


@app.middleware("http")                            # 中间件：包在所有路由外（主文档 3.8）
async def timing_middleware(request: Request,
                            call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Elapsed-Ms"] = f"{elapsed_ms:.1f}"
    return response


@app.get("/items/me")                              # 必须声明在 /items/{item_id} 之前（3.2 的坑）
def my_item():
    return {"item": "ME"}


@app.get("/items/{item_id}")
def get_item(item_id: int, q: str | None = None,   # 路径参数按类型注解解析；q 为查询参数
             admin: dict = Depends(require_admin),
             calls: dict = Depends(count_calls)):
    return {"item_id": item_id, "q": q, "admin": admin["user"], "calls": calls["calls"]}


@app.get("/calls")
def calls(c1: dict = Depends(count_calls), c2: dict = Depends(count_calls)):
    # 同一个依赖被声明两次——解析一次还是两次？
    return {"c1": c1["calls"], "c2": c2["calls"]}


def main() -> None:
    with TestClient(app) as client:                # 上下文管理器：启动/关闭生命周期
        r = client.get("/items/me")
        print("GET /items/me           ->", r.status_code, r.json())

        r = client.get("/items/42?q=abc")
        print("GET /items/42?q=abc     ->", r.status_code, r.json(),
              "| X-Elapsed-Ms 头:", r.headers.get("X-Elapsed-Ms") is not None)

        r = client.get("/items/not-a-number")      # 类型注解驱动校验：422
        print("GET /items/not-a-number ->", r.status_code, r.json()["detail"][0]["type"])

        r = client.get("/calls")                   # 依赖缓存：一次请求只解析一次
        print("GET /calls              ->", r.status_code, r.json())

    assert r.json()["c1"] == r.json()["c2"], "同一请求内同名依赖应只解析一次"
    print("断言通过：同一请求内同名依赖只解析一次（请求级缓存生效）")


if __name__ == "__main__":
    main()
