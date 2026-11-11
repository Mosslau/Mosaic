"""AI 平台 D1 dummy 服务入口。

运行：
    ./run.sh --port 18081 --ledger var/ledger.jsonl
"""

from mosaic_kernel.service import run

from .contracts import CONTRACTS

if __name__ == "__main__":
    run("ai-service-registry-dummy", CONTRACTS, default_port=18181)
