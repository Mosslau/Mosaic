#!/usr/bin/env bash
# init-minio-bucket.sh — 建 Flink 检查点要用的 MinIO bucket（幂等）
#
# 为什么需要它: **S3 文件系统不会自动建 bucket** —— Flink 配了 `s3://…` 而 bucket 不存在时，
#   检查点会直接失败：作业照样 RUNNING，只是永远拿不到检查点 → **恢复能力静默失效**
#   （正是本次要修的那类"看起来没问题"的故障，故把它变成一条可执行的前置判据）。
#
# 实现说明（含一处自我更正）: `mc` 客户端**就在 minio server 镜像里**（`/usr/bin/mc`，实测），
#   不需要额外的 minio/mc 镜像 —— 先前那句"server 镜像里没有 mc"是我一次引号写错的探测得出的错误结论。
#
# 用法: bash scripts/init-minio-bucket.sh
# 退出码: 0=就绪; 1=失败
set -uo pipefail

BUCKET="${FLINK_CHECKPOINT_BUCKET:-mosaic-flink}"
MINIO_CT="${MINIO_CONTAINER:-mosaic-minio}"

echo "=== 建 Flink 检查点 bucket ==="
if docker exec "${MINIO_CT}" sh -c "
    mc alias set ov http://localhost:9000 ov_minio ov_minio_2026 >/dev/null 2>&1 || exit 1
    mc mb --ignore-existing ov/${BUCKET} >/dev/null 2>&1 || exit 1
    mc ls ov/${BUCKET} >/dev/null 2>&1 || exit 1
  " 2>/dev/null; then
  echo "  ✅ bucket 就绪: ${BUCKET}"
else
  echo "  ❌ 建 bucket 失败: 确认容器 ${MINIO_CT} 已起且健康（docker compose ps）"
  exit 1
fi
