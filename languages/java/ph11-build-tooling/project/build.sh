#!/usr/bin/env bash
# ph11 阶段项目构建脚本：clean → package → 运行 app 演示
# 用法：./build.sh          （标准命令, 联网环境首次会从 Maven Central 拉取依赖/插件）
#       ./build.sh offline  （离线模式 mvn -o, 使用本地仓库缓存——本环境实测即此模式, 沙箱禁止写 ~/.m2）
set -euo pipefail
cd "$(dirname "$0")"

if [[ "${1:-}" == "offline" ]]; then
  MVN="mvn -o"
else
  MVN="mvn"
fi

echo "==> 1. 全量构建（reactor 按依赖顺序构建 common → app）"
$MVN clean package

echo "==> 2. 运行 app（示例输入 demo.txt）"
java -jar app/target/app-1.0-SNAPSHOT.jar demo.txt
