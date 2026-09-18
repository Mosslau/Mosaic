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
import os, pathlib, re, sys

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
    # 文档重构（总分结构）后的旧文件名：改一处漏三处的高发区
    '接入层与车端接入网关设计-v1.md': '已更名为 docs/01-接入层设计-v1.md',
    'GB32960-二进制协议与字段映射-v1.md': '已更名为 docs/02-GB32960协议规格-v1.md',
    '接入层示例集-v1.md': '已更名为 docs/03-验收示例集-v1.md',
    '接入层端到端流程说明-v1.md': '已删除，内容已拆入各篇（见 ingest/README.md 文档分工表）',
    'docs/README.md': '阅读地图已并入 ingest/README.md，不再单设',
    '接入层与车端接入网关设计》': '简称统一为《接入层设计》（该全名仅保留为文档标题，见 §13 修订记录）',
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
            pre = line[:m.start()]
            # 跨文档判据：前面出现《简称》/“设计文档”/ 任意 .md 文件名（含表格里的 `docs/01-x.md` | §0 写法）
            if '《' in pre or '设计文档' in pre or '.md' in pre:
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
        # 修订记录是**历史陈述**(记录当时的数字), 不参与"当前事实"校验 ——
        # 与检查①对 '增补'/'修订' 的豁免口径保持一致(否则每次修订都会被自己判失败)。
        if allowed(line) or '增补' in line or '修订' in line:
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
if [str(p) for p in owners] != ['ingest/docs/01-接入层设计-v1.md']:
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
      # 修订记录/增补表按历史快照写（会提到已删除或已改名的文档），不做目标存在性校验
      if allowed(line) or '增补' in line or '修订' in line:
        continue
      for m in re.finditer(r'[《`]([^》`\s]*\.md)[》`]', line):
        ref = m.group(1)
        cands = [pathlib.Path(ref), p.parent / ref,
                 pathlib.Path('ingest/docs') / pathlib.Path(ref).name,
                 pathlib.Path('ingest') / ref, pathlib.Path('deploy') / ref]
        base = pathlib.Path(ref).name
        if ref.strip('.') == 'md':          # 泛指写法(如"任何 `.md` 里的")不算引用
            continue
        if any(ch in ref for ch in '*{<'):  # 通配/模板写法(如 `ingest/device-*/README.md`)不算具体引用
            continue
        if base.startswith('xx'):           # 占位示例(如《../docs/xx.md》反面写法)不算引用
            continue
        if not any(c.exists() for c in cands) and not ref.startswith('http'):
            miss.append(f"{p} → {ref}")
for x in miss:
    bad(f"引用目标不存在: {x}")
if not miss:
    ok("全部引用目标存在")

# ---------- ⑦ 引用密度（总分结构：服务手册自足，层文档不反向依赖） ----------
# 规则来源：文档重构方案 B —— "按服务模块拆开 + 总分结构"，
#   服务手册（ingest/device-*/README.md）必须自足：跑/配/验/排障都在篇内，
#   只允许 ≤3 个"往上一层看设计"的指针；层文档（ingest/docs/*.md）不写服务操作步骤。
print("⑦ 引用密度（服务手册 ≤3 个层文档指针）")
ALIAS = {
    '接入层设计': 'ingest/docs/01-接入层设计-v1.md',
    'GB32960 映射': 'ingest/docs/02-GB32960协议规格-v1.md',
    '示例集': 'ingest/docs/03-验收示例集-v1.md',
}
LIMIT = {'manual': 3, 'layer': 4}      # manual=ingest/device-*/README.md；layer=ingest/docs/*.md
def canon(t, self_p):
    t = t.strip().strip('`')
    if t in ALIAS:
        return ALIAS[t]
    if not t.endswith('.md'):
        return None                     # 非文档名（如《OceanVerse 架构总览》标题式引用）不计入
    for c in (pathlib.Path(t), self_p.parent / t,
              pathlib.Path('ingest/docs') / pathlib.Path(t).name,
              pathlib.Path('ingest') / t, pathlib.Path('deploy') / t):
        if c.exists():
            return os.path.normpath(str(c))   # 归一化 ../ 形式，避免同一文档被数两次
    return None
for p in MD:
    sp = str(p)
    if sp.startswith('ingest/device-') and p.name == 'README.md':
        kind, limit = 'manual', LIMIT['manual']
    elif sp.startswith('ingest/docs/'):
        kind, limit = 'layer', LIMIT['layer']
    else:
        continue
    targets = {c for c in (canon(m.group(1), p)
                           for m in re.finditer(r'《([^》]+)》', p.read_text(encoding='utf-8')))
               if c and c != sp}
    if len(targets) > limit:
        bad(f"{sp}（{'服务手册' if kind == 'manual' else '层文档'}）指向 {len(targets)} 篇其它文档 > {limit}: "
            + ', '.join(sorted(x.split('/')[-1] for x in targets)))
    else:
        ok(f"{sp} 指针 {len(targets)}/{limit}")

print()
if fail:
    print(f"==== 文档校验: {fail} 项未通过 ====")
    sys.exit(1)
print("==== 文档校验: 全部通过 ====")
PY