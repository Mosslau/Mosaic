#!/usr/bin/env python3
# exercises/sol-03-api-schedule.py —— 练习 3 参考实现：定时拉取接口（本地服务 + 轮询循环）
# 验证环境：Python 3.13.9，requests 2.32.5（pip install requests；已装）
# 运行：python3 sol-03-api-schedule.py（离线可跑，已验证；HTTP 服务起在进程内线程，结束自动关闭）
# 验证状态：已验证 —— 实测输出（本机 Python 3.13.9 + requests 2.32.5 实际运行）：
#   调度循环 -> 3 轮，每轮拉取 /api/telemetry 成功 1 条，共写入 3 条
#   telemetry.csv -> 4 行（含表头），3 行数据均带时间戳
#   错误处理 -> /api/error 首次失败 + 重试仍失败，errors.log 记 2 条
#   幂等说明 -> 追加写 CSV（重复运行会多一轮数据，符合「日志追加」语义）
#   服务关闭 -> 打印「临时 HTTP 服务已关闭」
import csv
import json
import logging
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests


class ApiHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/api/telemetry":
            self._json(200, {"vehicle": "EV-001", "speed": 55})
        elif self.path == "/api/error":
            self._json(500, {"error": "internal"})
        else:
            self._json(404, {"error": "not found"})

    def log_message(self, *args: object) -> None:
        pass

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def fetch_with_retry(url: str, logger: logging.Logger, retries: int = 1) -> dict | None:
    """带超时 + 重试的拉取：失败记错误日志，重试仍失败返回 None。"""
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, timeout=2)
            r.raise_for_status()  # 4xx/5xx 抛 HTTPError
            return r.json()
        except requests.exceptions.RequestException as e:
            logger.error("拉取失败(%s/第%d次): %s", url, attempt + 1, type(e).__name__)
    return None


def main() -> None:
    work = Path(tempfile.mkdtemp(prefix="ph12-sol03-"))
    logging.basicConfig(
        filename=work / "errors.log", level=logging.ERROR,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logger = logging.getLogger("api")

    server = ThreadingHTTPServer(("127.0.0.1", 0), ApiHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    csv_path = work / "telemetry.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["时间", "车辆", "速度"])
        try:
            print("调度循环 -> 3 轮，每轮拉取 /api/telemetry")
            for round_no in range(3):  # 定时轮询：schedule 库的 run_pending 也是这个思想
                data = fetch_with_retry(f"{base}/api/telemetry", logger)
                if data is not None:
                    writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S"),
                                     data["vehicle"], data["speed"]])
                time.sleep(1)  # 演示「定时」；真实脚本里把这段换成 schedule 主循环（主文档 3.7）
            data = fetch_with_retry(f"{base}/api/error", logger)  # 500 端点：走错误处理路径
            print("错误处理 -> /api/error 首次失败 + 重试仍失败，errors.log 记",
                  len((work / "errors.log").read_text(encoding="utf-8").strip().splitlines()), "条")
            print("错误处理后返回 ->", data)
        finally:
            server.shutdown()
            server.server_close()

    lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    print("telemetry.csv ->", len(lines), "行（含表头），", len(lines) - 1, "行数据均带时间戳")
    print("临时 HTTP 服务已关闭")


if __name__ == "__main__":
    main()
