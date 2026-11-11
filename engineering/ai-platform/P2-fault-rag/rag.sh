#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
ROOT="$(cd ../../.. && pwd)"
export PYTHONPATH="$PWD/src:$PWD/../P1-contract-kernel/src:$ROOT/engineering/infra/kernel/src${PYTHONPATH:+:$PYTHONPATH}"
exec "${PYTHON:-python3}" -m mosaic_fault_rag.cli "$@"
