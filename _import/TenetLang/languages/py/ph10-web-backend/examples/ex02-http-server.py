# examples/ex02-http-server.py —— http.server 标准库基线：线程内起服务、请求、关闭
# 验证环境：Python 3.13.9，httpx 0.28.1
# 运行：python3 ex02-http-server.py（离线可跑，已验证）
# 说明：用 http.server.ThreadingHTTPServer 在**线程内**起一个真实 HTTP 服务，
#       绑定 127.0.0.1 端口 0（操作系统分配高位空闲端口，无端口冲突），
#       请求完成后 shutdown() + server_close() + join() 干净关闭——脚本结束不留任何进程。
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx


class DemoHandler(BaseHTTPRequestHandler):
    """最简业务处理器：GET / 返回文本，GET /health 返回 JSON。"""

    def do_GET(self) -> None:                     # 按 HTTP 方法分发：do_GET/do_POST/...
        if self.path == "/health":
            body = json.dumps({"status": "ok", "service": "http.server"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = "hello from stdlib http.server\n".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        pass                                      # 关掉默认的访问日志，保持输出干净


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), DemoHandler)   # 端口 0 = 系统分配
    port = server.server_address[1]               # 从绑定结果取实际端口（高位随机）
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"服务已在线程内启动: http://127.0.0.1:{port}")

    try:
        with httpx.Client(timeout=5) as client:   # 客户端视角验证接口契约（主文档 3.1）
            r1 = client.get(f"http://127.0.0.1:{port}/")
            print("GET /       ->", r1.status_code, r1.text.strip())
            r2 = client.get(f"http://127.0.0.1:{port}/health")
            print("GET /health ->", r2.status_code, r2.json())
    finally:
        server.shutdown()                          # 停止 serve_forever
        server.server_close()                      # 释放端口
        thread.join(timeout=5)
        print("服务已关闭，端口已释放")


if __name__ == "__main__":
    main()
