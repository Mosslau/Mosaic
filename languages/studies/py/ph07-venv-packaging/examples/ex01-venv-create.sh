#!/usr/bin/env bash
# examples/ex01-venv-create.sh —— 创建并激活 venv + 安装依赖 + 验证隔离（完整命令序列）
# 来源：07-venv-packaging.md 第 6 章示例 1
# 验证环境：Python 3.13.12（macOS / Linux，bash/zsh）；Windows 激活命令见行内注释
# 运行：bash ex01-venv-create.sh（在临时目录演练，退出后自动清理）
# 验证状态：已验证

set -euo pipefail

# 1. 在临时目录创建项目（避免污染真实目录）
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT        # 脚本退出时自动清理临时目录
cd "$WORK_DIR"
echo "工作目录：$WORK_DIR"

# 2. 创建虚拟环境
python3 -m venv .venv

# 3. 激活（POSIX）。Windows cmd 用 .venv\Scripts\activate，PowerShell 用 .venv\Scripts\Activate.ps1
source .venv/bin/activate

# 4. 确认解释器指向 .venv/bin/python
which python

# 5. 升级 pip 并安装依赖
python -m pip install --upgrade pip --quiet
python -m pip install requests --quiet
python -c "import requests; print('requests 版本:', requests.__version__)"

# 6. 退出虚拟环境
deactivate

# 7. 验证隔离：系统环境没有 requests，应报 ModuleNotFoundError
if python3 -c "import requests" 2>/dev/null; then
    echo "注意：系统环境也装有 requests（本机已全局安装），隔离验证跳过"
else
    echo "隔离验证通过：系统环境无法 import requests（ModuleNotFoundError）"
fi
