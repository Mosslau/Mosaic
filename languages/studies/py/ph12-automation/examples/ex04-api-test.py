#!/usr/bin/env python3
# examples/ex04-api-test.py —— 接口测试：requests 打本地临时 HTTP 服务（离线）
# 验证环境：Python 3.13.9，requests 2.32.5（pip install requests）
# 运行：python3 ex04-api-test.py（离线可跑，已验证；本地服务起在 127.0.0.1 随机端口，结束自动关闭）
# 说明：对应主文档 3.4。用 http.server 起一个临时 API（进程内线程），requests 实测
#       GET/POST/404/超时四类路径——离线复现「接口测试」的完整闭环。
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests


class ApiHandler(BaseHTTPRequestHandler):
    """迷你设备 API：GET /health、GET /devices、POST /devices、GET /slow（睡 1.5s）。"""

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(200, {"status": "ok"})
        elif self.path == "/devices":
            self._json(200, {"devices": ["EV-001", "EV-002", "EV-003"]})
        elif self.path == "/slow":
            import time
            time.sleep(1.5)
            self._json(200, {"slow": True})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path == "/devices":
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)  # 读掉请求体
            self._json(201, {"created": "EV-004"})
        else:
            self._json(404, {"error": "not found"})

    def log_message(self, *args: object) -> None:  # 关掉默认访问日志噪音
        pass

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), ApiHandler)  # 端口 0 = 随机端口
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        r = requests.get(f"{base}/health", timeout=2)  # 超时是铁律：别让脚本挂死
        print("GET /health ->", r.status_code, r.json(), "| Content-Type:", r.headers["Content-Type"])

        r = requests.post(f"{base}/devices", json={"device_id": "V004"}, timeout=2)
        print("POST /devices ->", r.status_code, r.json())

        r = requests.get(f"{base}/nope", timeout=2)
        try:
            r.raise_for_status()  # 4xx/5xx 抛 HTTPError——接口测试的标准做法
        except requests.exceptions.HTTPError as e:
            print("GET /nope ->", r.status_code, "| raise_for_status 抛出:", type(e).__name__)

        try:
            requests.get(f"{base}/slow", timeout=0.3)  # 服务端睡 1.5s > 超时 0.3s
        except requests.exceptions.Timeout as e:
            print("GET /slow -> 超时:", type(e).__name__)
    finally:
        server.shutdown()  # 干净关闭，不留进程
        server.server_close()
        print("临时 HTTP 服务已关闭")


if __name__ == "__main__":
    main()
