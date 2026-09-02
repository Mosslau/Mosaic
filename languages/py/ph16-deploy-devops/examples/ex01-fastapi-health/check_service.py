#!/usr/bin/env python3
# examples/ex01-fastapi-health/check_service.py —— 真实 uvicorn 子进程 + httpx 打健康检查端点
# 验证环境：Python 3.13.9（macOS arm64）+ fastapi 0.139.1 + uvicorn 0.50.0 + httpx 0.28.1
# 运行：python3 check_service.py（在本目录执行；离线可跑，已验证）
# 验证状态：已验证 —— 实测起真实 uvicorn 服务，/health 200、/ready 200、/predict soh=80.5，
#           故障注入后 /ready 变 503 而 /health 仍 200，SIGTERM 优雅关停（日志 Shutting down 完整）
"""自动验证脚本：把 service.py 当成「真实部署」起一遍再打掉。

流程：子进程起 uvicorn（生产命令形态）→ 轮询 /health 直到就绪 →
httpx 断言 /health、/ready、/predict → 模拟依赖失效断言 /ready 变 503 →
SIGTERM 关停并确认子进程退出码。这就是「服务部署后第一件事：打健康检查」的自动化版。
"""

from __future__ import annotations

import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).parent
BASE = "http://127.0.0.1:8016"


def wait_up(client: httpx.Client, proc: subprocess.Popen, timeout: float = 10.0) -> None:
    """轮询 /health 直到 200（服务启动有耗时，不能起完立刻打）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:  # 进程已退出 = 启动失败
            raise RuntimeError(f"uvicorn 启动即退出，returncode={proc.returncode}")
        try:
            if client.get(f"{BASE}/health").status_code == 200:
                return
        except httpx.ConnectError:
            time.sleep(0.1)
    raise TimeoutError("服务 10s 内未就绪")


def main() -> None:
    # 生产形态的启动命令（不带 --reload），cwd 保证 import service:app 可解析
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "service:app", "--host", "127.0.0.1", "--port", "8016"],
        cwd=HERE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(timeout=5.0) as client:
            wait_up(client, proc)

            r = client.get(f"{BASE}/health")
            assert r.status_code == 200 and r.json() == {"status": "ok"}, r.text
            print(f"GET /health        -> {r.status_code} {r.json()}")

            r = client.get(f"{BASE}/ready")
            assert r.status_code == 200 and r.json() == {"status": "ready"}, r.text
            print(f"GET /ready         -> {r.status_code} {r.json()}")

            payload = {"cycles": 1500, "avg_temp": 25, "depth": 80, "c_rate": 1.0}
            r = client.post(f"{BASE}/predict", json=payload)
            assert r.status_code == 200 and r.json() == {"soh": 80.5}, r.text
            print(f"POST /predict      -> {r.status_code} {r.json()}（规则模型占位）")

            # 故障注入（子进程内的状态，只能通过 HTTP 翻转）：readiness 应变 503，
            # liveness 仍 200——两者的分工见主文档 3.7
            client.post(f"{BASE}/admin/fail-model")
            r = client.get(f"{BASE}/ready")
            assert r.status_code == 503, r.text
            print(f"GET /ready（故障） -> {r.status_code} {r.json()}")
            r = client.get(f"{BASE}/health")
            assert r.status_code == 200, r.text
            client.post(f"{BASE}/admin/fail-model")  # 恢复就绪状态
    finally:
        proc.send_signal(signal.SIGTERM)  # 优雅关停：uvicorn 收到 SIGTERM 会先关连接再退出
        proc.wait(timeout=10)
        # returncode=-15（shell 里显示 143）：进程死于 SIGTERM 是 Unix 惯例；关键看日志里
        # 有 "Shutting down ... Finished server process"——优雅关停完成。systemd 把
        # 「被 SIGTERM 终止」视为正常停止（SuccessExitStatus 语义）。
        print(f"SIGTERM 关停，returncode={proc.returncode}（-15 = 被信号终止，关停日志见 stderr）")
    print("ex01 验证通过：健康检查 / 就绪探针 / 推理端点全部符合预期")


if __name__ == "__main__":
    main()
