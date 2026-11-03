#!/usr/bin/env bash
# Mosaic 一键校验：按域分发，每个域用自己的运行环境与 pytest 配置。
#
#   ./verify.sh          # 文档契约 + 算法测试 + Agent 运行时
#   ./verify.sh --site   # 追加语言域文档站构建（需要网络，较慢）
#
# 退出码：0 全部通过 / 1 有域失败 / 2 无失败但有域跳过（跳过的域不算通过）。
#
# 为什么分域跑而不用一条 pytest：三个域的 pytest 配置互斥。仓库根 pytest.ini 用
# --import-mode=importlib 服务算法域聚合运行；engineering 的子项目用同目录导入，
# 只能在 prepend 模式下收集。互相收集会在收集期直接失败，所以各域自带 rootdir。

set -uo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT}"

DOCS_PYTHON="${DOCS_PYTHON:-python3}"
RUNTIME_DIR="engineering/ai-platform/agent-platform/agent-service/python-agent-runtime"

RUN_SITE=0
for arg in "$@"; do
  case "${arg}" in
    --site) RUN_SITE=1 ;;
    -h | --help)
      sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "未知参数：${arg}（可用：--site、--help）" >&2
      exit 64
      ;;
  esac
done

PASSED=""
FAILED=""
SKIPPED=""

section() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }

record() {
  case "$2" in
    pass) PASSED="${PASSED}  ✅ $1"$'\n' ;;
    fail) FAILED="${FAILED}  ❌ $1"$'\n' ;;
    skip) SKIPPED="${SKIPPED}  ⚠️  $1"$'\n' ;;
  esac
}

run() {
  local name="$1"
  shift
  section "${name}"
  if "$@"; then
    record "${name}" pass
  else
    record "${name}" fail
  fi
}

# --- ① 文档契约（语言域 + 算法域）------------------------------------------
if command -v "${DOCS_PYTHON}" >/dev/null 2>&1; then
  run "文档契约 · 语言域（章节/链接/产物纪律）" \
    "${DOCS_PYTHON}" .dsh/skills/tenetlang-notes/scripts/validate.py --links
  run "文档契约 · 算法域（索引/状态/锚定/违禁 import）" \
    "${DOCS_PYTHON}" .dsh/skills/mindspring-lab/scripts/validate.py
else
  echo "[verify] 找不到 ${DOCS_PYTHON}，跳过文档域（可用 DOCS_PYTHON=... 指定解释器）" >&2
  record "文档契约 · 语言域" skip
  record "文档契约 · 算法域" skip
fi

# --- ② 算法域测试 -----------------------------------------------------------
if [[ -x algorithms/.venv/bin/python ]]; then
  run "算法域测试（575 项）" \
    bash -c 'cd algorithms && .venv/bin/python -m pytest -q'
elif command -v uv >/dev/null 2>&1; then
  run "算法域测试（575 项）" \
    bash -c 'cd algorithms && uv run pytest -q'
else
  echo "[verify] 未找到 algorithms/.venv 或 uv；先执行 (cd algorithms && uv sync --extra dev)" >&2
  record "算法域测试" skip
fi

# --- ③ Agent 运行时（pytest + ruff + docstring + 空白检查）-------------------
if [[ -x "${RUNTIME_DIR}/.venv/bin/python" ]]; then
  run "Agent 运行时（pytest/ruff/docstring）" "${RUNTIME_DIR}/scripts/verify.sh"
else
  echo "[verify] 未找到 ${RUNTIME_DIR}/.venv；先执行 (cd ${RUNTIME_DIR} && uv sync)" >&2
  record "Agent 运行时" skip
fi

# --- ④ 语言域文档站（可选）--------------------------------------------------
if ((RUN_SITE)); then
  if [[ -d languages/website/node_modules ]]; then
    run "语言域文档站构建" bash -c 'cd languages/website && npm run build'
  else
    echo "[verify] 未找到 languages/website/node_modules；先执行 (cd languages/website && npm install)" >&2
    record "语言域文档站构建" skip
  fi
fi

# --- 汇总 -------------------------------------------------------------------
printf '\n\033[1m== 校验汇总 ==\033[0m\n'
[[ -n "${PASSED}" ]] && printf '%b' "${PASSED}"
[[ -n "${SKIPPED}" ]] && printf '%b' "${SKIPPED}"
[[ -n "${FAILED}" ]] && printf '%b' "${FAILED}"

if [[ -n "${FAILED}" ]]; then
  echo
  echo "结论：失败。"
  exit 1
fi
if [[ -n "${SKIPPED}" ]]; then
  echo
  echo "结论：无失败，但有域被跳过——跳过的域不算验证通过（见上方提示安装依赖）。"
  exit 2
fi
echo
echo "结论：全部通过。"
exit 0
