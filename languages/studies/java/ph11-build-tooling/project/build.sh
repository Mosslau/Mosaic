#!/usr/bin/env bash
# ph11 阶段项目构建脚本：clean → package → 运行 app 演示
# 用法：./build.sh          （标准命令, 联网环境首次会从 Maven Central 拉取依赖/插件）
#       ./build.sh offline  （离线模式 mvn -o, 使用本地仓库缓存——本环境实测即此模式, 沙箱禁止写 ~/.m2）
set -euo pipefail
cd "$(dirname "$0")"

# 前置检查：脚本依赖 mvn 与 java, 缺失时给出明确错误而不是含糊的 command not found
command -v mvn >/dev/null 2>&1 || { echo "错误: 未找到 mvn, 请先安装 Maven 3.9+" >&2; exit 1; }
command -v java >/dev/null 2>&1 || { echo "错误: 未找到 java, 请先安装 JDK 17+" >&2; exit 1; }

if [[ "${1:-}" == "offline" ]]; then
  MVN="mvn -o"
else
  MVN="mvn"
fi

echo "==> 1. 全量构建（reactor 按依赖顺序构建 common → app）"
$MVN clean package

echo "==> 2. 运行 app（示例输入 demo.txt）"
# 产物 jar 名带版本号（app-1.0-SNAPSHOT.jar）, 用通配匹配当前版本——升版本号时无需同步改本脚本
# （|| true 兜底: pipefail 下 compgen 无匹配返回非零, 不能让脚本在赋值行静默退出）
APP_JAR=$(compgen -G "app/target/app-*.jar" | head -n 1 || true)
if [[ -z "$APP_JAR" ]]; then
  echo "错误: 未找到 app/target/app-*.jar, 请确认 mvn clean package 成功" >&2
  exit 1
fi
java -jar "$APP_JAR" demo.txt
