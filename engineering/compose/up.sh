#!/usr/bin/env bash
# 一键起共享 D0 底座（7 个服务默认全起）。
#   ./up.sh                  # kafka / postgres / redis / prometheus / grafana / minio / vault
#   ./up.sh kafka postgres   # 只起指定服务（调试用）
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon 不可用：先启动 Docker Desktop / colima" >&2
  exit 1
fi

docker compose up -d --wait "$@"
echo
docker compose ps
