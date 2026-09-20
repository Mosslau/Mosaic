#!/usr/bin/env bash
# test-compose-budget.sh — 给"内存预算门禁"做负向对照（判据本身的体检）
#
# 为什么需要它:
#   门禁自己也会退化成**僵尸判据** —— 2026-09-20 实测: `check-compose-budget.sh` 的判据 ④
#   （ClickHouse 进程内上限 < mem_limit）长期打印"跳过", 因为它在 compose 里找一个早已挪进
#   limits.xml 的变量名。而"跳过"和"通过"在输出里长得一样, 没人发现这条不等式**名义上有门禁、
#   实际没跑**（同批复评还发现它只核对 compose 内部, README 的数字漂移了一版也没人抓）。
#   只在正常态跑绿, 证明不了判据有鉴别力 —— 所以把负向对照固化下来。
#
# 做法: 每则对照在**隔离的假树**里施加扰动（复制 4 个文件到 .tmp-budget-selftest/,
#   门禁靠 $(dirname $0)/.. 定位根, 所以假树照原样摆 scripts/ 与 deploy/）, 跑完即弃 ——
#   不备份/不还原真实文件, 中断也不会留下半改状态。
#
# 用法: bash scripts/test-compose-budget.sh
# 退出码: 0=正常态绿且每则扰动都按预期变红; 1=有对照不成立（门禁失去鉴别力）
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$ROOT/.tmp-budget-selftest"
SBOX="$TMP/repo"
LIMITS_REL="deploy/clickhouse/config.d/limits.xml"
trap 'rm -rf "$TMP"' EXIT

setup() {
  rm -rf "$SBOX"
  mkdir -p "$SBOX/scripts" "$SBOX/deploy/clickhouse/config.d"
  cp "$ROOT/scripts/check-compose-budget.sh" "$SBOX/scripts/"
  cp "$ROOT/deploy/docker-compose.yaml" "$ROOT/deploy/README.md" "$SBOX/deploy/"
  cp "$ROOT/$LIMITS_REL" "$SBOX/$LIMITS_REL"
}

gate() { bash "$SBOX/scripts/check-compose-budget.sh" 2>&1; }

# 在假树里做一次字面替换; 找不到 old 就**中止**（扰动没生效 = 对照本身坏了, 继续跑只会得到假结论）
perturb() { # $1=相对路径 $2=old $3=new
  python3 - "$SBOX/$1" "$2" "$3" <<'PY' || { echo "  ⛔ 扰动失败（对照本身有问题）: $1"; exit 2; }
import pathlib, sys
p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding='utf-8')
old = sys.argv[2]
if old not in s:
    print(f"找不到待替换文本: {old!r}", file=sys.stderr)
    sys.exit(9)
p.write_text(s.replace(old, sys.argv[3]), encoding='utf-8')
PY
}

# 删掉某一行（按子串匹配）
drop_line() { # $1=相对路径 $2=子串
  python3 - "$SBOX/$1" "$2" <<'PY' || { echo "  ⛔ 扰动失败（对照本身有问题）: $1"; exit 2; }
import pathlib, sys
p = pathlib.Path(sys.argv[1])
lines = p.read_text(encoding='utf-8').split('\n')
keep = [l for l in lines if sys.argv[2] not in l]
if len(keep) == len(lines):
    print(f"找不到要删除的行: {sys.argv[2]!r}", file=sys.stderr)
    sys.exit(9)
p.write_text('\n'.join(keep), encoding='utf-8')
PY
}

pass=0; fail=0

check_case() { # $1=对照名 $2=期望命中的关键词
  local out rc
  out=$(gate); rc=$?
  if [[ $rc -ne 0 ]] && grep -qF "$2" <<< "$out"; then
    echo "  ✅ $1"
    pass=$((pass + 1))
  else
    echo "  ❌ $1 —— 期望变红(exit≠0 且命中「$2」)，实际 exit ${rc}"
    sed 's/^/      /' <<< "$out"
    fail=$((fail + 1))
  fi
  setup
}

echo "=== 内存预算门禁体检（负向对照） ==="

# ---- 基线：正常态必须绿（否则后面"变红"毫无意义） ----
setup
out=$(gate); rc=$?
if [[ $rc -eq 0 ]]; then
  echo "  ✅ 基线：正常态全过（exit 0）"
  pass=$((pass + 1))
else
  echo "  ❌ 基线：正常态就不绿 —— 先修门禁本身"
  sed 's/^/      /' <<< "$out"
  fail=$((fail + 1))
fi

# ---- 判据 ④：成对约束与四个隐蔽失效方式 ----
perturb "$LIMITS_REL" '<max_server_memory_usage>1610612736<' '<max_server_memory_usage>4000000000<'
check_case "A 进程内上限（3814 MiB）越线 mem_limit（2560 MiB）" "≥ mem_limit"

drop_line "deploy/docker-compose.yaml" "limits.xml:/etc/clickhouse-server"
check_case "B limits.xml 没被 compose 挂进容器（死配置）" "没有把它挂进容器"

perturb "$LIMITS_REL" '</max_server_memory_usage>' '</max_server_memory_usage>
    <max_server_memory_usage_to_ram_ratio>0</max_server_memory_usage_to_ram_ratio>'
check_case "C ratio=0（实测语义是关闭上限）" "关闭内存上限"

rm -f "$SBOX/$LIMITS_REL"
check_case "D limits.xml 整个缺失" "缺少 $LIMITS_REL"

# 缓存边界未显式声明（镜像默认 mark 5 GiB / uncompressed 8 GiB 会与查询抢额度）
perturb "$LIMITS_REL" '<mark_cache_size>134217728</mark_cache_size>' ''
check_case "K 缓存上限未显式声明（退回镜像默认）" "未显式声明"

perturb "deploy/docker-compose.yaml" '      CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT: 1' '      CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT: 1
      CLICKHOUSE_MAX_SERVER_MEMORY_USAGE: 900000000'
check_case "E 无效环境变量被当成生效配置写" "不生效"

# ---- 判据 ⑤：文档数字 vs compose ----
perturb "deploy/README.md" '= **5120 MiB**' '= **4480 MiB**'
check_case "F README 合计漂移" "声称合计"

perturb "deploy/README.md" 'ClickHouse 2560m' 'ClickHouse 1280m'
check_case "G README 单服务值漂移（2026-09-20 实际发生过的那处）" "compose 是"

perturb "deploy/README.md" ' + Redis 256m
' '
'
check_case "H README 漏写一个服务（新增容器场景）" "未覆盖这些服务"

perturb "deploy/README.md" '的 **65%**' '的 **30%**'
check_case "I 百分比与「合计 / VM 容量」不自洽" "占 VM 容量"

# ---- 判据 ②：合计超预算（compose 与 README 同步改动 → ⑤ 仍绿, 只有 ②③ 该响） ----
perturb "deploy/docker-compose.yaml" '    mem_limit: 2560m' '    mem_limit: 5120m'
perturb "deploy/README.md" ' + ClickHouse 2560m' ' + ClickHouse 5120m'
out=$(gate); rc=$?
if [[ $rc -ne 0 ]] && grep -qF "> 预算" <<< "$out"; then
  echo "  ✅ J 合计超预算（文档已同步, 故只有预算判据该响）"
  pass=$((pass + 1))
else
  echo "  ❌ J 合计超预算 —— 期望变红并命中「> 预算」，实际 exit ${rc}"
  sed 's/^/      /' <<< "$out"
  fail=$((fail + 1))
fi

echo
echo "==== 门禁体检: ${pass} 项符合预期, ${fail} 项异常 ===="
exit $(( fail > 0 ))
