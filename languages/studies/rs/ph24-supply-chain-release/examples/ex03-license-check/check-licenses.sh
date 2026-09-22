#!/usr/bin/env bash
# examples/ex03-license-check/check-licenses.sh —— 许可证清单自动核对
#
# 验证状态：脚本在零依赖工程与含三方依赖工程上实测通过（bash + python3 + cargo 1.92.0）；
#   它只基于 crate 的 license 元数据核对——无法替代人工对 license-file / 缺失字段的判断。
#
# 用法：./check-licenses.sh [cargo 工程目录]   （缺省为当前目录）
# 输出：逐包 license 表 + 汇总行（核对 N 个包 / allow 命中 X / 需人工确认 Y），非零退出码表示有需人工项
#
# 依赖：cargo（cargo metadata）、python3（解析 JSON）；无 jq 依赖。需要联网解析 registry 元数据。

set -euo pipefail

if ! command -v cargo >/dev/null 2>&1; then
    echo "错误：找不到 cargo。请先 export PATH=\"\$HOME/.cargo/bin:\$PATH\"" >&2
    exit 2
fi

PROJECT_DIR="${1:-$(pwd)}"
cd "$PROJECT_DIR"

# allow 清单（与 deny.toml 的 [licenses].allow 保持同一集合；按分发模式裁剪，见主文档 3.4）
ALLOW_LICENSES="MIT|Apache-2.0|BSD-3-Clause|ISC|MPL-2.0|0BSD|Unicode-3.0|Zlib"

echo "== 工程：$(sed -n 's/^name *= *"\([^"]*\)".*/\1/p' Cargo.toml | head -1) =="
echo "== allow 清单：${ALLOW_LICENSES//|/ /}（含 OR 组合）=="

METADATA="$(cargo metadata --format-version 1)"   # JSON 经 argv 传给 python，stdin 留给脚本本身
python3 - "$ALLOW_LICENSES" "$METADATA" <<'PY'
import json, re, sys

allow_pattern = sys.argv[1]
data = json.loads(sys.argv[2])

rows, ok, manual = [], 0, 0
for p in sorted(data["packages"], key=lambda x: x["name"]):
    lic = (p.get("license") or "").strip()
    # OR/AND 表达式拆开：任一成分命中 allow 集合即通过（OR 语义），否则需人工确认
    parts = [s.strip() for s in re.split(r"\s+OR\s+|\s+AND\s+", lic) if s.strip()]
    hit = any(re.search(r"(?<![A-Za-z0-9.-])(" + allow_pattern + r")(?![A-Za-z0-9.-])", pt) for pt in parts)
    if parts and hit:
        ok += 1
        flag = "OK"
    else:
        manual += 1
        flag = "MANUAL"
    rows.append(f"{flag:<7} {p['name']:<30} {p['version']:<12} {lic or '<未声明>'}")

print(f"\n{'状态':<7} {'crate':<30} {'version':<12} license")
print("-" * 72)
for r in rows:
    print(r)

n = len(rows)
print(f"\n汇总：依赖核对 {n} 个 / allow 命中 {ok} / 需人工确认 {manual}")
if manual:
    print("结论：存在需人工确认项 → 排查 license 缺失或 allow 清单外的许可（主文档 3.6）")
    sys.exit(1)
print("结论：全部命中 allow 清单")
PY
