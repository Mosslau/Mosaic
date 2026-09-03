#!/usr/bin/env python3
# examples/ex01-fastapi-health/check_service.py —— 真实 uvicorn 子进程 + httpx 打健康检查端点
# 验证环境：Python 3.13.9（macOS arm64）+ fastapi 0.139.1 + uvicorn 0.50.0 + httpx 0.28.1
# 运行：python3 check_service.py（在本目录执行；离线可跑，已验证）
# 验证状态：已验证 —— 实测起真实 uvicorn 服务，/health 200、/ready 200、/predict soh=80.5，
#           故障注入后 /ready 变 503 而 /health 仍 200；SIGTERM 后退出码 -15（shell 143），
#           并从捕获的 stderr 断言优雅关停日志 "Shutting down" 与 "Finished server process"
#           2026-09 复跑实测：uvicorn 0.50.0（Python 3.13.9, macOS arm64）优雅关停日志齐备后
#           进程仍以 SIGTERM 终止（returncode=-15 / shell 143），断言按实测值保留
"""自动验证脚本：把 service.py 当成「真实部署」起一遍再打掉。

流程：子进程起 uvicorn（生产命令形态）→ 轮询 /health 直到就绪 →
httpx 断言 /health、/ready、/predict → 模拟依赖失效断言 /ready 变 503 →
SIGTERM 关停：断言子进程退出码，并检查捕获的 stderr 含 uvicorn 的优雅关停日志
（Shutting down / Finished server process）。这就是「服务部署后第一件事：
打健康检查」的自动化版。
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
    # 生产形态的启动命令（不带 --reload），cwd 保证 import service:app 可解析。
    # stderr 捕获到内存（PIPE）：uvicorn 的日志量很小（启动 + 数个请求），
    # 不会撑满管道缓冲；关停后从捕获内容断言优雅关停日志。
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "service:app", "--host", "127.0.0.1", "--port", "8016"],
        cwd=HERE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
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
        logs = proc.stderr.read() if proc.stderr is not None else ""
        # returncode=-15（shell 里显示 143）：进程死于 SIGTERM 是 Unix 惯例。
        # 2026-09 本机实测（uvicorn 0.50.0 + Python 3.13.9）：优雅关停日志
        # （Shutting down / Finished server process）齐备后，进程仍以 -15 被信号终止，
        # 而非自行 exit 0——systemd 把「被 SIGTERM 终止」视为正常停止
        # （Restart=on-failure 不触发重启，见 ex05 unit 注释），因此断言保留 -15。
        assert proc.returncode == -signal.SIGTERM, proc.returncode
        assert "Shutting down" in logs, logs
        assert "Finished server process" in logs, logs
        print(f"SIGTERM 关停，returncode={proc.returncode}（-15 = 被信号终止）")
        markers = [
            line.strip()
            for line in logs.splitlines()
            if ("Shutting down" in line) or ("Finished server process" in line)
        ]
        print("关停日志（stderr 捕获）：" + " | ".join(markers))
    print("ex01 验证通过：健康检查 / 就绪探针 / 推理端点 / 优雅关停全部符合预期")


if __name__ == "__main__":
    main()
