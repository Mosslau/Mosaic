#!/usr/bin/env bash
# project/springboot-deploy-template/purejava/app-smoke.sh —— 纯 Java 部署主链冒烟自检
# 用 javac/java/curl 真实验收「打包 → 启动 → 探活 → 外置配置 → 优雅停机」这条部署主链，
# 语义对应主文档：可执行 jar（3.2）、健康探活（3.5/3.11）、配置外置（3.2）、优雅停机（3.11）。
# 教学点：容器/K8s/流水线替你做的人肉动作，在这里被显式做一遍——看懂它，读 docker/k8s 清单时
#        每个探针/参数都在跟这段脚本「对暗号」。
# 用法（在 purejava/ 目录下执行）：
#   ./app-smoke.sh                       # 用 PATH 里的 javac/java
#   JAVA_HOME=/opt/homebrew/opt/openjdk@17 ./app-smoke.sh
# 验证环境：OpenJDK 17 + curl + jar（JDK 自带）
# 验证状态：已验证（OpenJDK 17.0.18 + macOS 本机实测全部 PASS）
set -euo pipefail

# ---- 工具链探测：优先 JAVA_HOME，其次 PATH；找不到 openjdk@17 时给出提示 ----
if [ -n "${JAVA_HOME:-}" ]; then
  JAVAC="$JAVA_HOME/bin/javac"
  JAVA="$JAVA_HOME/bin/java"
  JAR="$JAVA_HOME/bin/jar"
else
  JAVAC="$(command -v javac || true)"
  JAVA="$(command -v java || true)"
  JAR="$(command -v jar || true)"
  if [ -z "$JAVAC" ] && [ -x /opt/homebrew/opt/openjdk@17/bin/javac ]; then
    JAVAC=/opt/homebrew/opt/openjdk@17/bin/javac
    JAVA=/opt/homebrew/opt/openjdk@17/bin/java
    JAR=/opt/homebrew/opt/openjdk@17/bin/jar
  fi
fi
for t in "$JAVAC" "$JAVA" "$JAR"; do
  [ -n "$t" ] || { echo "缺少 javac/java/jar，请装 OpenJDK 17 或用 JAVA_HOME 指定"; exit 1; }
done

PORT="${PUREJAVA_PORT:-18099}"
BASE="http://127.0.0.1:${PORT}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
PASS=0; FAIL=0
ok()   { echo "PASS $1"; PASS=$((PASS + 1)); }
ko()   { echo "FAIL $1 -- $2"; FAIL=$((FAIL + 1)); }

wait_health() {   # 最多等 15s 探活
  local i=0
  while [ "$i" -lt 15 ]; do
    if curl -fsS --max-time 2 "$BASE/actuator/health" >/dev/null 2>&1; then return 0; fi
    i=$((i + 1)); sleep 1
  done
  return 1
}

echo "== 1/4 编译并打包成可执行 jar（对应 3.2：java -jar 直接跑，无需 classpath）"
"$JAVAC" -d "$WORK/out" src/purejava/MiniApp.java
"$JAR" --create --file "$WORK/mini-app.jar" --main-class purejava.MiniApp -C "$WORK/out" .
"$JAVA" -jar "$WORK/mini-app.jar" >"$WORK/log1.log" 2>&1 &
PID1=$!
if wait_health; then ok "可执行 jar 启动后 /actuator/health 可探活"; else ko "jar 启动探活" "见 $WORK/log1.log"; kill "$PID1" 2>/dev/null || true; fi

echo "== 2/4 健康端点与默认配置（profile 默认 dev）"
health_body="$(curl -fsS "$BASE/actuator/health")"
case "$health_body" in
  *'"status":"UP"'*) ok "health 端点返回 UP（body: $health_body）" ;;
  *) ko "health body" "$health_body" ;;
esac
ping_body="$(curl -fsS "$BASE/ping")"
case "$ping_body" in
  *'"profile":"dev"'*) ok "/ping 默认 profile=dev" ;;
  *) ko "默认 profile" "$ping_body" ;;
esac

echo "== 3/4 SIGTERM 优雅停机（对应 3.11：先拒新再收尾，日志可见）"
kill -TERM "$PID1"
set +e; wait "$PID1"; RC=$?; set -e
if grep -q 'shutdown_complete' "$WORK/log1.log"; then
  ok "SIGTERM 后优雅收尾，日志含 shutdown_complete"
else
  ko "优雅停机日志" "$(tail -3 "$WORK/log1.log")"
fi
if [ "$RC" -eq 143 ] || [ "$RC" -eq 0 ]; then
  ok "进程按信号约定退出（rc=$RC，SIGTERM 期望 143）"
else
  ko "退出码" "rc=$RC"
fi

echo "== 4/4 配置外置（-Dapp.profile=prod 覆盖，对应 3.2 配置随环境注入）"
"$JAVA" -Dapp.profile=prod -jar "$WORK/mini-app.jar" >"$WORK/log2.log" 2>&1 &
PID2=$!
wait_health || { echo "第二次启动失败"; tail -5 "$WORK/log2.log"; exit 1; }
ping2="$(curl -fsS "$BASE/ping")"
case "$ping2" in
  *'"profile":"prod"'*) ok "启动参数注入 profile=prod" ;;
  *) ko "profile 覆盖" "$ping2" ;;
esac
kill -TERM "$PID2"; wait "$PID2" 2>/dev/null || true

echo
echo "RESULT passed=$PASS failed=$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
