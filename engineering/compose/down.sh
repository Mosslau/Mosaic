#!/usr/bin/env bash
# 停共享 D0 底座。默认保留数据卷。
#   ./down.sh          # 停服务，保留卷
#   ./down.sh --volumes  # 连卷一起删（数据清空）
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
docker compose down --remove-orphans "$@"
