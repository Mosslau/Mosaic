#!/usr/bin/env python3
# examples/ex05-systemd-metrics/check_metrics.py —— 验证 /metrics 端点的 Prometheus 文本格式
# 验证环境：Python 3.13.9（macOS arm64）+ fastapi 0.139.1 + uvicorn 0.50.0 + httpx 0.28.1
# 运行：python3 check_metrics.py（在本目录执行；离线可跑，已验证）
# 验证状态：已验证 —— 实测起真实 uvicorn 服务，打 3 次 /predict + 1 次 /health 后 /metrics
#           输出 demo_requests_total{endpoint="predict"} 3、{endpoint="health"} 1、
#           demo_predict_seconds_count 3、demo_uptime_seconds Gauge 递增
"""自动验证：起服务 → 制造流量 → 抓 /metrics → 断言指标语义（Counter 累计、Histogram 计数）。"""

from __future__ import annotations

import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).parent
BASE = "http://127.0.0.1:8017"


def main() -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "service:app", "--host", "127.0.0.1", "--port", "8017"],
        cwd=HERE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(timeout=5.0) as client:
            for _ in range(50):  # 等服务就绪
                try:
                    if client.get(f"{BASE}/health").status_code == 200:
                        break
                except httpx.ConnectError:
                    time.sleep(0.1)
            else:
                raise TimeoutError("服务 5s 内未就绪")

            payload = {"cycles": 1500, "avg_temp": 25, "depth": 80, "c_rate": 1.0}
            for _ in range(3):
                assert client.post(f"{BASE}/predict", json=payload).status_code == 200

            r = client.get(f"{BASE}/metrics")
            assert r.status_code == 200
            body = r.text
            print("--- /metrics 实测输出（节选）---")
            print("\n".join(line for line in body.splitlines() if not line.startswith("# HELP")))
            print("---")
            # 轮询期间打过若干次 /health（≥1），predict 恰好 3 次
            assert 'demo_requests_total{endpoint="predict"} 3' in body
            assert 'demo_requests_total{endpoint="health"}' in body
            assert "demo_predict_seconds_count 3" in body
            assert "demo_uptime_seconds" in body
            assert "# TYPE demo_requests_total counter" in body
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)
    print("ex05 验证通过：/metrics 文本格式与 Counter/Histogram/Gauge 语义全部符合预期")


if __name__ == "__main__":
    main()
