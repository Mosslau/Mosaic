#!/usr/bin/env bash
# 起 D1 dummy 服务（数据默认 18080 / AI 默认 18081）。
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
ROOT="$(cd ../../.. && pwd)"
PKG="mosaic_data_contracts"
export PYTHONPATH="$PWD/src:$ROOT/engineering/infra/kernel/src${PYTHONPATH:+:$PYTHONPATH}"
exec "${PYTHON:-python3}" -m "$PKG.service" "$@"
