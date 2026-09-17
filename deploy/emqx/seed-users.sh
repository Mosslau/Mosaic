#!/usr/bin/env bash
# seed-users.sh — 向 8883(TLS) 监听器的内置认证库批量写入设备凭证(一车一密, 开发用)
#
# 用法: ./seed-users.sh [起始序号] [数量]   例: ./seed-users.sh 0 100 → OV00000000..OV00000099
# 密码规则(仅开发!): pw-{VIN}。生产换随机强密码 + 档案服务管理(设计文档 §8.2)。
# 依赖: ov-emqx 容器运行中; 原理 = emqx eval 调 emqx_authn_chains:add_user/3
set -euo pipefail

START=${1:-0}
COUNT=${2:-100}
CHAIN="ssl:default"
AUTHN="password_based:built_in_database"

ok=0; skip=0
for i in $(seq "$START" $((START + COUNT - 1))); do
  vin=$(printf "OV%08d" "$i")
  result=$(docker exec ov-emqx emqx eval \
    "R = emqx_authn_chains:add_user(binary_to_atom(<<\"$CHAIN\">>), <<\"$AUTHN\">>, #{user_id => <<\"$vin\">>, password => <<\"pw-$vin\">>, is_superuser => false}), io:format(\"~p\", [element(1, R)])." \
    2>/dev/null | head -1)   # eval 结尾会多打一行 ok, 取第一行才是我们的结果
  case "$result" in
    ok*) ok=$((ok+1));;      # "ok" / "okok"(eval 结尾会多打一行 ok, 用前缀匹配)
    *)   skip=$((skip+1));;  # already_exist 等
  esac
done
echo "✅ 完成: 新增 $ok, 跳过(已存在等) $skip"
echo "   核对总数: docker exec ov-emqx emqx eval 'io:format(\"~p\", [length(mnesia:dirty_all_keys(emqx_authn_mnesia))]).'"
