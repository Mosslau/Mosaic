#!/usr/bin/env bash
# examples/ex05-uv-quickstart.sh —— 用 uv 快速管理环境（uv venv / uv add / uv sync 对比 pip）
# 来源：07-venv-packaging.md 第 6 章示例 5
# 验证环境：Python 3.13.12；需本机已安装 uv（未安装则脚本提示并退出）
# 运行：bash ex05-uv-quickstart.sh（在临时目录演练，退出后自动清理）
# 验证状态：已验证

set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
    echo "本机未安装 uv，跳过演示。安装：brew install uv 或 curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 0
fi

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
cd "$WORK_DIR"

# 1. 生成骨架 + pyproject.toml
uv init demo
cd demo

# 2. 创建 .venv（等价 python -m venv .venv）
uv venv

# 3. 加依赖：自动写 pyproject.toml 并生成 uv.lock
uv add requests

# 4. 加开发依赖
uv add --dev pytest

# 5. 按 uv.lock 精确同步环境
uv sync

# 6. 在项目环境里运行（无需手动 activate）
uv run python -c "import requests; print('requests 版本:', requests.__version__)"

# 7. 安装指定 Python 版本并以其建环境（uv 自带 Python 管理）
# uv python install 3.12 && uv venv --python 3.12
