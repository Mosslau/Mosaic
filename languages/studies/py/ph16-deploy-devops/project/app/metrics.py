"""最小 Prometheus 指标注册表（ph16 project/app/metrics.py）。

不引第三方库，手写文本暴露格式（text/plain; version=0.0.4），教学上把
「Counter / Histogram / Gauge 到底是什么」摊开；生产直接换 prometheus_client，
端点形态与抓取协议完全一致。

多进程部署注意：指标是进程内的，--workers 4 时每个 worker 各记一份——
Prometheus 按实例抓取后聚合是正常形态；要精确的全局计数得用
prometheus_client 的 multiprocess 模式（本模板不展开）。
"""

from __future__ import annotations

import threading
import time


class MetricsRegistry:
    """线程安全的进程内指标：请求计数（按端点+状态码）+ 预测耗时 + 模型信息。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: dict[tuple[str, int], int] = {}
        self._predict_count = 0
        self._predict_sum = 0.0
        self._started_at = time.monotonic()
        self.model_type = "unknown"

    def record_request(self, endpoint: str, status: int) -> None:
        with self._lock:
            key = (endpoint, status)
            self._requests[key] = self._requests.get(key, 0) + 1

    def record_predict(self, seconds: float) -> None:
        with self._lock:
            self._predict_count += 1
            self._predict_sum += seconds

    def render(self) -> str:
        """导出 Prometheus 文本格式（Gauge/Counter/Histogram 的最小骨架）。"""
        with self._lock:
            lines = [
                "# HELP bhealth_requests_total HTTP 请求总数（按端点与状态码）",
                "# TYPE bhealth_requests_total counter",
            ]
            for (endpoint, status), count in sorted(self._requests.items()):
                labels = f'endpoint="{endpoint}",status="{status}"'
                lines.append(f"bhealth_requests_total{{{labels}}} {count}")
            lines += [
                "# HELP bhealth_predict_seconds 预测耗时（histogram，count/sum 骨架）",
                "# TYPE bhealth_predict_seconds histogram",
                f"bhealth_predict_seconds_count {self._predict_count}",
                f"bhealth_predict_seconds_sum {self._predict_sum:.6f}",
                "# HELP bhealth_model_info 当前推理后端（1 = 生效；label 是类型）",
                "# TYPE bhealth_model_info gauge",
                f'bhealth_model_info{{model_type="{self.model_type}"}} 1',
                "# HELP bhealth_uptime_seconds 进程运行秒数",
                "# TYPE bhealth_uptime_seconds gauge",
                f"bhealth_uptime_seconds {time.monotonic() - self._started_at:.1f}",
                "",
            ]
        return "\n".join(lines)
