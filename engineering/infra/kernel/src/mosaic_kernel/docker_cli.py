"""容器内 CLI 桥：D2/D3/D4 早期用 `docker compose exec` 访问 Kafka/PG。

正式接入（SeaTunnel / JDBC / Flink）后替换本模块；在此之前的纵切、
烟测与查询脚本共用它，避免每个单元重复拼 docker 命令。
"""

import subprocess
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[5]
COMPOSE_FILE = REPO_ROOT / "engineering" / "infra" / "compose" / "docker-compose.yml"


def compose_exec(service: str, *args: str, stdin: Optional[str] = None) -> str:
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "exec", "-T", service] + list(args)
    proc = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "docker compose exec %s failed (%d): %s"
            % (service, proc.returncode, proc.stderr.strip()[:500])
        )
    return proc.stdout


def psql(sql: str) -> str:
    return compose_exec(
        "postgres",
        "psql", "-U", "mosaic", "-d", "mosaic",
        "-v", "ON_ERROR_STOP=1", "-q", "-f", "-",
        stdin=sql,
    )


def pg_query(sql: str) -> str:
    return compose_exec(
        "postgres",
        "psql", "-U", "mosaic", "-d", "mosaic", "-tAc", sql,
    ).strip()
