#!/usr/bin/env bash
# 一键起共享 D0 底座。
#   ./up.sh                  # 默认 5 个服务：kafka / postgres / redis / prometheus / grafana
#   ./up.sh --profile objectstore   # 追加 MinIO（需联网拉镜像）
#   ./up.sh --profile vault         # 追加 Vault（需联网拉镜像）
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon 不可用：先启动 Docker Desktop / colima" >&2
  exit 1
fi

docker compose up -d --wait "$@"
echo
docker compose ps
