#!/usr/bin/env bash
# seed-users.sh — 向 8883(TLS) 监听器的内置认证库批量写入设备凭证(一车一密, 开发用)
#
# 用法:
#   ./seed-users.sh [起始序号] [数量]        例: ./seed-users.sh 0 100    → OV00000000..OV00000099
#   ./seed-users.sh --vin OV20260001         按**显式 VIN** 灌单台(序号格式化放不下的大号 VIN)
#
# 密码规则(仅开发!): pw-{VIN}。生产换随机强密码 + 档案服务管理(设计文档 §8.2)。
# 依赖: ov-emqx 容器运行中; 原理 = emqx eval 调 emqx_authn_chains:add_user/3
#
# ⚠️ 前提与坑(2026-09-18 审计实测):
#   ① 凭证存放在 mnesia 的 `data/mnesia/<节点名>/` 下。若 EMQX 节点名随容器 IP 变化
#      (镜像 entrypoint 默认行为), 换 IP 就等于换了一个空库, 凭证"静默失效"且旧目录成为孤儿。
#      现在 compose 已固定 `EMQX_NODE__NAME=emqx@127.0.0.1`, 凭证可跨重建存活。
#   ② 容器重建/换节点名后必须**重新执行本脚本**, 否则 security-check 的 ①④ 会失败。
#   ③ 序号格式化是 %08d, 所以只能表达 0..99999999 以内的号; 更大的 VIN(如 OV20260001)
#      必须用 --vin 显式指定。
set -euo pipefail

CHAIN="ssl:default"
AUTHN="password_based:built_in_database"

add_one() {
  local vin="$1"
  local result
  result=$(docker exec ov-emqx emqx eval \
    "R = emqx_authn_chains:add_user(binary_to_atom(<<\"$CHAIN\">>), <<\"$AUTHN\">>, #{user_id => <<\"$vin\">>, password => <<\"pw-$vin\">>, is_superuser => false}), io:format(\"~p\", [element(1, R)])." \
    2>/dev/null | head -1)   # eval 结尾会多打一行 ok, 取第一行才是我们的结果
  case "$result" in
    ok*) return 0;;         # "ok" / "okok"(eval 结尾会多打一行 ok, 用前缀匹配)
    *)   return 1;;         # already_exist 等
  esac
}

total() {
  docker exec ov-emqx emqx eval 'io:format("~p", [length(mnesia:dirty_all_keys(emqx_authn_mnesia))]).' 2>/dev/null | head -1
}

if [[ "${1:-}" == "--vin" ]]; then
  VIN="${2:?用法: seed-users.sh --vin OV20260001}"
  if add_one "$VIN"; then
    echo "✅ 已写入: $VIN (密码 pw-$VIN)"
  else
    echo "ℹ️  已存在或写入被跳过: $VIN"
  fi
  echo "   核对总数: $(total)"
  exit 0
fi

START=${1:-0}
COUNT=${2:-100}

if ! [[ "$START" =~ ^[0-9]+$ && "$COUNT" =~ ^[0-9]+$ ]]; then
  echo "❌ 起始序号与数量必须为非负整数(大号 VIN 请用 --vin)" >&2
  exit 2
fi

ok=0; skip=0
for i in $(seq "$START" $((START + COUNT - 1))); do
  vin=$(printf "OV%08d" "$i")
  if add_one "$vin"; then ok=$((ok+1)); else skip=$((skip+1)); fi
done
echo "✅ 完成: 新增 $ok, 跳过(已存在等) $skip"
echo "   核对总数: $(total)"
