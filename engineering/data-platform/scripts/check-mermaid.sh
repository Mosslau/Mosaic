#!/usr/bin/env bash
# check-mermaid.sh — 校验文档里的 Mermaid 图能否渲染(语法/结构错误会让图整张废掉)
#
# 用法:
#   scripts/check-mermaid.sh                      # 校验全仓 docs/README 里的 mermaid 块
#   scripts/check-mermaid.sh ingest/README.md …   # 只校验指定文件
#
# 依赖: Docker(Rancher Desktop 等) + minlag/mermaid-cli 镜像。
# 说明: 挂载目录必须在 $HOME 下(Rancher 只共享 $HOME 给 VM, /tmp 挂不进),
#       故临时目录用仓库内 .tmp-mmdc/(已 gitignore)。
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$ROOT/.tmp-mmdc/mmd"
rm -rf "$TMP"; mkdir -p "$TMP"

if [ "$#" -gt 0 ]; then
  FILES=("$@")
else
  FILES=()
  while IFS= read -r f; do FILES+=("$f"); done < <(cd "$ROOT" && grep -rl '```mermaid' --include='*.md' . \
    | grep -v '^./.dsh/' | sed 's|^\./||' | sort)
fi

[ "${#FILES[@]}" -gt 0 ] || { echo "没有找到 mermaid 图"; exit 0; }

python3 - "$TMP" "${FILES[@]}" << 'PY'
import re, sys, pathlib, hashlib
tmp = pathlib.Path(sys.argv[1])
total = 0
for src in sys.argv[2:]:
    s = pathlib.Path(src).read_text(encoding='utf-8')
    tag = hashlib.md5(str(pathlib.Path(src).resolve()).encode()).hexdigest()[:6]
    for i, m in enumerate(re.findall(r'```mermaid\n(.*?)```', s, re.S), 1):
        (tmp / f"{tag}_{i}.mmd").write_text(m, encoding='utf-8')
        total += 1
        print(f"{src}\t#{i}\t{len(m.splitlines())}行")
print(f"-- 共 {total} 张待校验 --")
PY

fail=0; n=0
for f in "$TMP"/*.mmd; do
  [ -e "$f" ] || continue
  n=$((n+1))
  if docker run --rm -v "$TMP":/data minlag/mermaid-cli \
       -i "/data/$(basename "$f")" -o "/data/$(basename "$f" .mmd).svg" >/dev/null 2>&1; then
    echo "  ✅ $(basename "$f")"
  else
    echo "  ❌ $(basename "$f")  首行: $(head -1 "$f")"
    fail=$((fail+1))
  fi
done
echo "==== 渲染校验: 共 $n 张, 失败 $fail ===="
[ "$fail" -eq 0 ] || echo "提示: 先在本地用 mermaid 预览定位语法问题(常见: 标签里的引号/括号未转义、节点 ID 重复)"
exit $(( fail > 0 ))
