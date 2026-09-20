#!/usr/bin/env bash
# check-compose-budget.sh — 容器内存预算门禁
#
# 为什么需要它（2026-09-20，第 1、2 步评审）:
#   `mem_limit` 只约束**单个**容器, 不阻止"上限之和 > 物理内存"。
#   第九轮补齐 MySQL/Redis 后, 八容器 mem_limit 合计 **6.88 GiB**, 而 Rancher VM 实测只有
#   **6.2 GiB**（docker info MemTotal）; 同时 ClickHouse 实测已吃到 1.9 GiB / 2 GiB(94.5%)。
#   也就是说: 账面上就已经超配, 再拉起 MySQL 就是整机 OOM —— 而当时**没有任何检查会发现**,
#   只能靠人肉算术（README §3 那段"内存预算"注释就是这么来的）。
#   本脚本把那段算术变成可执行判据。
#
# 判据:
#   ① 每个服务都必须有 mem_limit（漏一个就等于没有上限）
#   ② 合计 mem_limit ≤ 预算上限（默认 4.75 GiB; 可用 OV_BUDGET_MIB 覆盖）
#   ③ 若 VM 容量可探测（本机 docker info）: 合计 ≤ VM 容量 × 0.85
#      —— 留 15% 给 dockerd/VM 自身, 否则"合法配置"仍会把整机压死
#   ④ 已知成对约束: ClickHouse 的进程内上限必须 < 其 mem_limit;
#      Redis 的 maxmemory 必须显著小于其 mem_limit（否则 cgroup 先杀, 表现为反复重启）
#
# 退出码: 0=通过; 1=超预算/漏上限; 2=用法/环境问题
#
# 用法: bash scripts/check-compose-budget.sh
#       OV_BUDGET_MIB=5120 bash scripts/check-compose-budget.sh   # 临时放宽(需说明理由)
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE="$ROOT/deploy/docker-compose.yaml"
BUDGET_MIB="${OV_BUDGET_MIB:-4864}"   # 4.75 GiB（八容器实测合计 4608 MiB + 余量；VM 实测 5921 MiB 的 82%）

[[ -f "$COMPOSE" ]] || { echo "找不到 $COMPOSE" >&2; exit 2; }

pass=0; fail=0
ok()  { echo "  [OK]   $1"; pass=$((pass+1)); }
bad() { echo "  [FAIL] $1"; fail=$((fail+1)); }
info(){ echo "         $1"; }

echo "=== 容器内存预算检查 ==="
echo "compose: $COMPOSE | 预算上限: ${BUDGET_MIB} MiB"
echo

# ---------- 解析 compose（不依赖 yq: 用 python3 的标准库做最小解析） ----------
parsed=$(python3 - "$COMPOSE" <<'PY'
import re, sys, pathlib

text = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
svc = None
limits = {}
in_services = False
for raw in text.split('\n'):
    line = raw.rstrip()
    if line.startswith('services:'):
        in_services = True
        continue
    if in_services and line and not line.startswith(' ') and line.endswith(':'):
        in_services = False   # 到了顶层 volumes:/networks:
    if not in_services:
        continue
    m = re.match(r'^  ([a-z0-9_-]+):\s*$', line)
    if m:
        svc = m.group(1)
        continue
    m = re.match(r'^\s+mem_limit:\s*(\S+)', line)
    if m and svc:
        limits[svc] = m.group(1)

def to_mib(v):
    v = v.strip().strip('"').strip("'")
    m = re.match(r'^(\d+(?:\.\d+)?)\s*([kmgKMG]?)[bB]?$', v)
    if not m:
        return None
    n, unit = float(m.group(1)), m.group(2).lower()
    factor = {'': 1/1048576, 'k': 1/1024, 'm': 1, 'g': 1024}[unit]
    return n * factor

total = 0.0
for name, val in sorted(limits.items()):
    mib = to_mib(val)
    if mib is None:
        print(f"PARSE_FAIL {name} {val}")
        continue
    total += mib
    print(f"SVC {name} {val} {mib:.0f}")
print(f"TOTAL {total:.0f}")
PY
) || { echo "解析 compose 失败" >&2; exit 2; }

missing=$(python3 - "$COMPOSE" <<'PY'
import re, sys, pathlib
text = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
names, in_services = [], False
for line in text.split('\n'):
    if line.startswith('services:'):
        in_services = True
        continue
    if in_services and line and not line.startswith(' ') and line.endswith(':'):
        in_services = False
    if in_services:
        m = re.match(r'^  ([a-z0-9_-]+):\s*$', line)
        if m:
            names.append(m.group(1))
with_limit = set(re.findall(r'^\s+mem_limit:', text, re.M))
have = set()
cur = None
for line in text.split('\n'):
    m = re.match(r'^  ([a-z0-9_-]+):\s*$', line)
    if m:
        cur = m.group(1)
    if re.match(r'^\s+mem_limit:', line) and cur:
        have.add(cur)
print(' '.join(n for n in names if n not in have))
PY
)

echo "① 每服务都有 mem_limit"
if [[ -z "${missing// /}" ]]; then
  ok "全部服务均声明 mem_limit"
else
  bad "以下服务缺 mem_limit（等于没有上限）: $missing"
fi

total=$(printf '%s\n' "$parsed" | awk '/^TOTAL/ {print $2}')
printf '%s\n' "$parsed" | awk '/^SVC/ {printf "         %-12s %-8s %s MiB\n", $2, $3, $4}'

echo
echo "② 合计 vs 预算上限"
if [[ -z "$total" ]]; then
  bad "无法计算合计"
elif (( $(printf '%.0f' "$total") <= BUDGET_MIB )); then
  ok "合计 $(printf '%.0f' "$total") MiB ≤ 预算 ${BUDGET_MIB} MiB"
else
  bad "合计 $(printf '%.0f' "$total") MiB > 预算 ${BUDGET_MIB} MiB → 整机 OOM 风险（mem_limit 不阻止上限之和超物理内存）"
  info "对策: 压低单个上限, 或 OV_BUDGET_MIB 显式放宽（须同时确认 VM 内存真的够）"
fi

echo
echo "③ 合计 vs VM 容量（本机可探测时）"
vm_mib=""
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  vm_bytes=$(docker info --format '{{.MemTotal}}' 2>/dev/null)
  if [[ "$vm_bytes" =~ ^[0-9]+$ ]] && (( vm_bytes > 0 )); then
    vm_mib=$(( vm_bytes / 1024 / 1024 ))
  fi
fi
if [[ -z "$vm_mib" ]]; then
  info "探测不到 VM 容量（docker 不可用或非 Linux VM）→ 跳过（CI 上属预期）"
else
  cap=$(( vm_mib * 85 / 100 ))
  if (( $(printf '%.0f' "$total") <= cap )); then
    ok "合计 $(printf '%.0f' "$total") MiB ≤ VM 容量 ${vm_mib} MiB 的 85%（${cap} MiB）"
  else
    bad "合计 $(printf '%.0f' "$total") MiB > VM 容量 ${vm_mib} MiB 的 85%（${cap} MiB）→ 留不出 dockerd/VM 自身的余量"
  fi
fi

echo
echo "④ 成对约束（进程内上限必须小于 cgroup 硬杀线）"
ch_inner=$(grep -oE 'CLICKHOUSE_MAX_SERVER_MEMORY_USAGE: *[0-9]+' "$COMPOSE" | grep -oE '[0-9]+$' || true)
ch_limit=$(grep -A 30 '^  clickhouse:' "$COMPOSE" | grep -oE 'mem_limit: *[0-9]+m' | head -1 | grep -oE '[0-9]+' || true)
if [[ -n "$ch_inner" && -n "$ch_limit" ]]; then
  inner_mib=$(( ch_inner / 1024 / 1024 ))
  if (( inner_mib < ch_limit )); then
    ok "ClickHouse 进程内上限 ${inner_mib} MiB < mem_limit ${ch_limit} MiB"
  else
    bad "ClickHouse 进程内上限 ${inner_mib} MiB ≥ mem_limit ${ch_limit} MiB → cgroup 会先杀容器（表现为反复重启）"
  fi
else
  info "未同时找到 ClickHouse 进程内上限与 mem_limit → 跳过（若删掉了进程内上限, 请确认是有意的）"
fi

redis_mm=$(grep -oE 'REDIS_MAXMEMORY:-[0-9]+mb' "$COMPOSE" | grep -oE '[0-9]+' || true)
rd_limit=$(grep -A 40 '^  redis:' "$COMPOSE" | grep -oE 'mem_limit: *[0-9]+m' | head -1 | grep -oE '[0-9]+' || true)
if [[ -n "$redis_mm" && -n "$rd_limit" ]]; then
  if (( redis_mm * 100 <= rd_limit * 75 )); then
    ok "Redis maxmemory ${redis_mm} MiB ≤ mem_limit ${rd_limit} MiB 的 75%"
  else
    bad "Redis maxmemory ${redis_mm} MiB 相对 mem_limit ${rd_limit} MiB 过高 → 算上进程开销会触发 OOM kill"
  fi
else
  info "未同时找到 Redis maxmemory 与 mem_limit → 跳过"
fi

echo
echo "==== 预算检查: 通过 ${pass} 项, 异常 ${fail} 项 ===="
exit $(( fail > 0 ))
