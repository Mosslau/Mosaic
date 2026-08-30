#!/usr/bin/env bash
# examples/ex02-requirements-freeze.sh —— 生成 requirements.txt（freeze 快照）+ 全新环境一键复现
# 来源：07-venv-packaging.md 第 6 章示例 2
# 验证环境：Python 3.13.12（macOS / Linux，bash/zsh）
# 运行：bash ex02-requirements-freeze.sh（在临时目录演练，退出后自动清理）
# 验证状态：已验证

set -euo pipefail

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
cd "$WORK_DIR"

# ---- 环境 A：安装若干包后冻结 ----
echo "== 环境 A：建环境、装包、freeze =="
python3 -m venv .venv-a
.venv-a/bin/python -m pip install --quiet requests
.venv-a/bin/python -m pip freeze > requirements.txt
echo "--- requirements.txt 内容（含间接依赖，精确锁定）---"
cat requirements.txt

# ---- 环境 B：全新环境按清单一键复现 ----
echo "== 环境 B：新建环境，pip install -r 复现 =="
python3 -m venv .venv-b
.venv-b/bin/python -m pip install --quiet -r requirements.txt
.venv-b/bin/python -c "import requests; print('复现成功，requests 版本:', requests.__version__)"

# ---- 对比两个环境的包清单是否一致 ----
diff <(.venv-a/bin/python -m pip freeze) <(.venv-b/bin/python -m pip freeze) \
    && echo "两个环境的包清单完全一致"
