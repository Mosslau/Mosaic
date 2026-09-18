#!/usr/bin/env bash
# check-docs.sh — 文档事实校验（把人工审计固化成可重复执行的检查）
#
# 覆盖三类历史漂移（都曾真实发生）：
#   ① 禁用词/旧路径残留   —— 改一处漏三处（如 五包 / 11 项配置 / localhost:8080 / 旧目录名）
#   ② 跨文档引用歧义      —— 裸 §x.y 指向别的文档（如流程说明里的 §8-③ 实指映射文档）
#   ③ 数字声明 vs 代码事实 —— 配置项数 / 测试包数 等"易腐数字"
# 另含：topic/QoS 单一源、Mermaid 围栏嵌套、.md 引用目标存在性。
#
# 用法: scripts/check-docs.sh        # 在仓库根执行；失败即非零退出
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 - <<'PY'
import pathlib, re, sys

fail = 0
ALLOW = '<!-- check-docs:allow -->'   # 行级豁免: 元文档里描述"被禁模式"时使用

def allowed(line):
    return ALLOW in line
def bad(msg):
    global fail
    fail += 1
    print(f"  ❌ {msg}")
def ok(msg):
    print(f"  ✅ {msg}")

MD = [p for p in pathlib.Path('.').rglob('*.md')
      if '.git' not in p.parts and p.parts[:2] != ('.dsh', 'skills')]

# ---------- ① 禁用词/旧路径 ----------
BANNED = {
    '11 项配置': '配置项数已变为 12（新增 KAFKA_BIN_TOPIC）',
    '五包': '测试包数已变（现为 5 个测试包）',
    'localhost:8080': '本机开发端口固定 18080',
    'cmd/simulator': '模拟器已迁 ingest/device-simulator 并更名 http-simulator',
    'ingest/simulator': '模块已更名 ingest/device-simulator',
    'ingest/contracts': 'Go 绑定已更名为 ingest/device-contracts',
}
print("① 禁用词/旧路径扫描")
for pat, why in BANNED.items():
    hits = [(p, i) for p in MD for i, l in enumerate(p.read_text(encoding='utf-8').split('\n'), 1)
            if pat in l and '增补' not in l and '修订' not in l and not allowed(l)]
    if hits:
        bad(f"'{pat}' 残留（{why}）: " + ', '.join(f"{p}:{i}" for p, i in hits[:3]))
    else:
        ok(f"无 '{pat}'")

# ---------- ② 跨文档引用歧义 ----------
print("② 章节引用检查（同文件 §x.y 必须存在；带《》或'设计文档'视为跨文档引用）")
for p in MD:
    s = p.read_text(encoding='utf-8')
    secs = {m.group(1) for m in re.finditer(r'^#{2,4}\s+(\d+(?:\.\d+)?)', s, re.M)}
    for i, line in enumerate(s.split('\n'), 1):
        if allowed(line):
            continue
        for m in re.finditer(r'§(\d+(?:\.\d+)?)', line):
            if '《' in line[:m.start()] or '设计文档' in line[:m.start()]:
                continue
            if m.group(1) not in secs:
                bad(f"{p}:{i} 引用 §{m.group(1)} 但本文件无此章节 → {line.strip()[:60]}")
if fail == 0:
    ok("无歧义引用")

# ---------- ③ 数字声明 vs 代码事实 ----------
print("③ 数字声明 vs 代码")
cfg = pathlib.Path('ingest/device-gateway/internal/config/config.go').read_text(encoding='utf-8')
env_n = len(re.findall(r'env(?:Str|Int|Float|Bool|Dur|List)\("', cfg))
claimed = set()
for p in MD:
    for line in p.read_text(encoding='utf-8').split('\n'):
        if allowed(line):
            continue
        for m in re.finditer(r'(\d+)\s*项配置', line):
            claimed.add(int(m.group(1)))
if claimed and claimed != {env_n}:
    bad(f"文档声称配置项数 {sorted(claimed)}，代码实际 {env_n}")
else:
    ok(f"配置项数一致（{env_n}）")

pkgs = sorted({str(f.parent) for f in pathlib.Path('ingest/device-gateway').rglob('*_test.go')})
for p in MD:
    for m in re.finditer(r'gateway\s*(\d+)\s*个测试包', p.read_text(encoding='utf-8')):
        if int(m.group(1)) != len(pkgs):
            bad(f"{p}: 声称 gateway {m.group(1)} 个测试包，实际 {len(pkgs)}")
        else:
            ok(f"{p.name}: 测试包数一致（{len(pkgs)}）")

# ---------- ④ topic/QoS 单一源 ----------
print("④ topic/QoS 单一源")
TABLE = re.compile(r'\|\s*`?ov/\{vin\}/status`?\s*\|')
owners = [p for p in MD if TABLE.search(p.read_text(encoding='utf-8'))]
if [str(p) for p in owners] != ['ingest/docs/接入层与车端接入网关设计-v1.md']:
    bad(f"topic 表应只在设计文档 §4.2，实际出现在: {[str(p) for p in owners]}")
else:
    ok("topic/QoS 表唯一源 = 设计文档 §4.2")

# ---------- ⑤ Mermaid 围栏嵌套 ----------
print("⑤ Mermaid 围栏结构")
nested = 0
for p in MD:
    lines = p.read_text(encoding='utf-8').split('\n')
    for i, l in enumerate(lines):
        if l.startswith('```') and not l.startswith('```mermaid') and '```mermaid' in '\n'.join(lines[i+1:i+3]):
            bad(f"{p}:{i+1} 出现围栏嵌套（```xxx 紧跟 ```mermaid）")
            nested += 1
if nested == 0:
    ok("无嵌套围栏")

# ---------- ⑥ .md 引用目标存在 ----------
print("⑥ 文档引用目标存在性")
miss = []
for p in MD:
    for line in p.read_text(encoding='utf-8').split('\n'):
      if allowed(line):
        continue
      for m in re.finditer(r'[《`]([^》`\s]*\.md)[》`]', line):
        ref = m.group(1)
        cands = [pathlib.Path(ref), p.parent / ref,
                 pathlib.Path('ingest/docs') / pathlib.Path(ref).name,
                 pathlib.Path('ingest') / ref, pathlib.Path('deploy') / ref]
        if ref.strip('.') == 'md':      # 泛指写法(如"任何 `.md` 里的")不算引用
            continue
        if not any(c.exists() for c in cands) and not ref.startswith(('http', 'x.md')):
            miss.append(f"{p} → {ref}")
for x in miss:
    bad(f"引用目标不存在: {x}")
if not miss:
    ok("全部引用目标存在")

print()
if fail:
    print(f"==== 文档校验: {fail} 项未通过 ====")
    sys.exit(1)
print("==== 文档校验: 全部通过 ====")
PY
