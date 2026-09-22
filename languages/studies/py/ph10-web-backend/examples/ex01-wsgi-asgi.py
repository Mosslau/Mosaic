# examples/ex01-wsgi-asgi.py —— WSGI 与 ASGI 协议应用：两种服务器接口的离线直驱
# 验证环境：Python 3.13.9（stdlib 与 asyncio，无第三方依赖）
# 运行：python3 ex01-wsgi-asgi.py（离线可跑，已验证）
# 说明：本示例不起真实服务器——直接用假 environ/start_response 与假 (scope, receive, send)
#       驱动应用可调用对象，验证「WSGI 应用 = 同步函数 (environ, start_response)」、
#       「ASGI 应用 = 异步函数 (scope, receive, send)」这一协议本质（主文档 4.1）。
import asyncio
import json
from typing import Any
from wsgiref.util import setup_testing_defaults


# ---------- 1. WSGI 应用：接收 environ（请求描述），调用 start_response（响应头），返回字节 ----------
def wsgi_app(environ: dict, start_response: Any) -> list[bytes]:
    """最小 WSGI 应用：路由 '/' 返回文本，其余返回 JSON。"""
    path = environ["PATH_INFO"]
    if path == "/":
        body = b"hello wsgi\n"
        start_response("200 OK", [("Content-Type", "text/plain; charset=utf-8")])
    else:
        payload = json.dumps({"path": path, "method": environ["REQUEST_METHOD"]}).encode()
        body = payload
        start_response("200 OK", [("Content-Type", "application/json")])
    return [body]


def drive_wsgi() -> None:
    """模拟 WSGI 服务器：构造 environ，调用应用，收集响应。"""
    environ: dict = {}
    setup_testing_defaults(environ)              # wsgiref 填充一套真实形状的默认请求描述
    environ["REQUEST_METHOD"] = "GET"
    environ["PATH_INFO"] = "/api/status"

    captured: dict = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    body = b"".join(wsgi_app(environ, start_response))     # 应用是可调用对象，直接调用
    print("WSGI 应用直驱:")
    print("  status:", captured["status"])
    print("  headers:", captured["headers"])
    print("  body:", body.decode())


# ---------- 2. ASGI 应用：接收 (scope, receive, send) 的异步可调用对象 ----------
async def asgi_app(scope: dict, receive: Any, send: Any) -> None:
    """最小 ASGI 应用：只处理 http 请求，返回 JSON 响应。"""
    assert scope["type"] == "http"
    body = json.dumps({"path": scope["path"], "method": scope["method"]}).encode()
    await send({                                    # 先发响应头
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"application/json")],
    })
    await send({                                    # 再发响应体
        "type": "http.response.body",
        "body": body,
    })


async def drive_asgi() -> None:
    """模拟 ASGI 服务器：构造 scope，用收集器接收 send 的消息。"""
    messages: list[dict] = []

    async def receive() -> dict:                    # 本示例无请求体，receive 不会被真正调用
        return {"type": "http.request", "body": b""}

    async def send(message: dict) -> None:
        messages.append(message)

    scope = {"type": "http", "method": "GET", "path": "/devices/V001/telemetry"}
    await asgi_app(scope, receive, send)

    status = messages[0]["status"]
    body = json.loads(messages[1]["body"])
    print("ASGI 应用直驱:")
    print("  status:", status)
    print("  body:", body)


def main() -> None:
    drive_wsgi()
    print()
    asyncio.run(drive_asgi())


if __name__ == "__main__":
    main()
