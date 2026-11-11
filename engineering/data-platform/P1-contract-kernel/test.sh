#!/usr/bin/env bash
# 跑 D1 契约内核测试（标准库 unittest，不装第三方依赖）。
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
ROOT="$(cd ../../.. && pwd)"
export PYTHONPATH="$PWD/src:$ROOT/engineering/infra/kernel/src${PYTHONPATH:+:$PYTHONPATH}"
exec "${PYTHON:-python3}" -m unittest discover -s tests -t . -v
