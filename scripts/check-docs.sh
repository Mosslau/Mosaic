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
import json as json_mod
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
    'realtime/': '该层已更名为 warehouse/（流处理模块为 lakehouse/warehouse/streaming/，2026-09-20）',
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

# ---------- ⑧ 告警规则数 / 面板数 / DLQ stage 枚举（2026-09-20 补） ----------
# 背景: 第 1、2 步评审发现三类"检查①~⑦ 都抓不到"的漂移 ——
#   ① 告警规则文件加了 2 条, 但文档仍写 8 条(且运行态只加载了 8 条也无人发现);
#   ② Grafana 面板 JSON 加了图, 两处文档仍写旧数字(网关写 4 实际 5; codec 写 4 实际 6);
#   ③ DLQ stage 枚举散落多处, 新增 stage 靠人肉同步(历史上已漏改过两次)。
# 这三类都是"文档声明的数字 vs 机器事实", 与检查③同源, 故并入本门禁。
print("⑧ 告警规则数 / 面板数 / DLQ stage 枚举")

# --- ⑧.1 告警规则数 ---
RULE_FILE = pathlib.Path('deploy/prometheus/rules/oceanverse-alerts.yml')
rule_n = len(re.findall(r'^\s*- alert:', RULE_FILE.read_text(encoding='utf-8'), re.M))
alert_claims = set()
for p in MD:
    for line in p.read_text(encoding='utf-8').split('\n'):
        if allowed(line) or '增补' in line or '修订' in line:
            continue
        for m in re.finditer(r'(\d+)\s*条(?:告警|规则)', line):
            alert_claims.add(int(m.group(1)))
if alert_claims and alert_claims != {rule_n}:
    bad(f"文档声称告警规则数 {sorted(alert_claims)}，规则文件实际 {rule_n}")
else:
    ok(f"告警规则数一致（{rule_n}）")

# --- ⑧.2 Grafana 面板数(每个面板 JSON 的图数 vs 文档里的 "N 图" 声明) ---
DASH = {
    'device-gateway': pathlib.Path('deploy/grafana/provisioning/dashboards/device-gateway.json'),
    'device-codec': pathlib.Path('deploy/grafana/provisioning/dashboards/device-codec.json'),
    'realtime-metrics': pathlib.Path('deploy/grafana/provisioning/dashboards/realtime-metrics.json'),
}
dash_n = {}
for name, f in DASH.items():
    if not f.exists():
        bad(f"面板文件缺失: {f}")
        continue
    dash_n[name] = len(json_mod.loads(f.read_text(encoding='utf-8')).get('panels', []))
for p in MD:
    text = p.read_text(encoding='utf-8')
    for i, line in enumerate(text.split('\n'), 1):
        if allowed(line) or '增补' in line or '修订' in line:
            continue
        # 只校验"同一行里点了面板名 + 图数"的写法(如"网关面板(uid device-gateway，4 图：…)"）
        for name, n in dash_n.items():
            if name not in line:
                continue
            for m in re.finditer(r'(\d+)\s*图', line):
                if int(m.group(1)) != n:
                    bad(f"{p}:{i} 声称 {name} 面板 {m.group(1)} 图，实际 JSON {n} 图")
if fail == 0 and dash_n:
    ok("面板图数一致（" + ', '.join(f"{k}={v}" for k, v in sorted(dash_n.items())) + "）")

# --- ⑧.3 DLQ stage 枚举: 代码真实产出的 stage vs 文档/指标 HELP 里列的集合 ---
CODEC_MAIN = pathlib.Path('ingest/device-codec/cmd/server/main.go').read_text(encoding='utf-8')
code_stages = set(re.findall(r'Stage:\s*"([a-z_]+)"', CODEC_MAIN))
# 只计 process() 里真实的 DLQ 产出(排除结构体定义里的注释)
code_stages = {s for s in code_stages if s}
doc_claims = {}
for p in MD:
    for i, line in enumerate(p.read_text(encoding='utf-8').split('\n'), 1):
        if allowed(line) or '增补' in line or '修订' in line:
            continue
        for m in re.finditer(r'stage\s*∈\s*\{([^}]+)\}', line):
            got = {x.strip() for x in m.group(1).split(',') if x.strip()}
            doc_claims[f"{p}:{i}"] = got
metrics_help = pathlib.Path('ingest/device-codec/internal/metrics/metrics.go').read_text(encoding='utf-8')
for m in re.finditer(r'stage\s*∈\s*\{([^}]+)\}', metrics_help):
    doc_claims['metrics.go HELP'] = {x.strip() for x in m.group(1).split(',') if x.strip()}
if not code_stages:
    bad("未能从 codec 主程序解出任何 DLQ stage(解析规则失效?)")
else:
    for where, got in doc_claims.items():
        if got != code_stages:
            bad(f"{where} 的 stage 枚举 {sorted(got)} != 代码实际 {sorted(code_stages)}")
    if doc_claims and all(g == code_stages for g in doc_claims.values()):
        ok(f"DLQ stage 枚举一致（{len(code_stages)} 个: {', '.join(sorted(code_stages))}）")
    elif not doc_claims:
        bad("文档/指标 HELP 里没有找到任何 DLQ stage 枚举声明")


# ---------- ⑨ 实时层"口径三处一致"（2026-09-20 补） ----------
# 背景: 实时作业的口径散落在三处 —— lakehouse/warehouse/streaming/README.md（口径表·唯一源）、sql/00-common.sql（sink 与字段）、
#   clickhouse/init.sql（Kafka 引擎表/MV/目标表）。三者必须同步, 而"同步"靠人记就会漂（本仓已多次踩到）。
#   这里只机械化可判定的部分: 三个结果表名与三个结果 topic 是否在三处都出现。
#   （"阈值/窗口语义"是否一致属文字表述, 仍需人工评审; 门禁只钉能钉的。）
print("⑨ 实时层口径三处一致（README / sql / clickhouse）")
RT = {
    'lakehouse/warehouse/streaming/README.md': pathlib.Path('lakehouse/warehouse/streaming/README.md'),
    'lakehouse/warehouse/streaming/sql/00-common.sql': pathlib.Path('lakehouse/warehouse/streaming/sql/00-common.sql'),
    'lakehouse/warehouse/streaming/clickhouse/init.sql': pathlib.Path('lakehouse/warehouse/streaming/clickhouse/init.sql'),
}
missing_files = [k for k, p in RT.items() if not p.exists()]
if missing_files:
    bad("实时层文件缺失: " + ', '.join(missing_files))
else:
    texts = {k: p.read_text(encoding='utf-8') for k, p in RT.items()}
    TABLES = ['ads_vehicle_online_1m', 'ads_fault_count_1m', 'ads_high_temp_battery_1m']
    TOPICS = ['ov.ads.vehicle_online_1m.v1', 'ov.ads.fault_count_1m.v1', 'ov.ads.high_temp_battery_1m.v1']
    rt_problems = []
    for t in TABLES:
        for k, txt in texts.items():
            if t not in txt:
                rt_problems.append(f"结果表 {t} 未出现在 {k}")
    for tp in TOPICS:
        for k, txt in texts.items():
            if tp not in txt:
                rt_problems.append(f"结果 topic {tp} 未出现在 {k}")
    # sink 的 topic 必须与 ClickHouse Kafka 引擎表的 kafka_topic_list 一一对应（防"改了一边"）
    for tp in TOPICS:
        if f"'topic'                        = '{tp}'" not in texts['lakehouse/warehouse/streaming/sql/00-common.sql']:
            rt_problems.append(f"sink 未声明 topic {tp}（00-common.sql）")
        if f"kafka_topic_list = '{tp}'" not in texts['lakehouse/warehouse/streaming/clickhouse/init.sql']:
            rt_problems.append(f"ClickHouse 引擎表未订阅 {tp}（init.sql）")
    if rt_problems:
        for m in rt_problems:
            bad(m)
    else:
        ok(f"三处一致（{len(TABLES)} 张结果表 / {len(TOPICS)} 个结果 topic）")


print()
if fail:
    print(f"==== 文档校验: {fail} 项未通过 ====")
    sys.exit(1)
print("==== 文档校验: 全部通过 ====")
