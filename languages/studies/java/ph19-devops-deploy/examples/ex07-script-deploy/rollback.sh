#!/usr/bin/env bash
# examples/ex07-script-deploy/rollback.sh —— 手工回滚脚本（对应主文档 3.12「发布必须可回滚」）
# 教学点：
#   1. 回滚本质 = 把运行态退回「已知良好的上一个版本」，前提是旧 jar 被保留（backup）
#   2. 与 K8s 的 rollout undo / helm rollback 同语义：这里是 systemd 世界的「版本回退」
# 验证状态：语法已通过本机 bash -n 校验；实际执行需 Linux + systemd + 已备份旧版本
set -euo pipefail

APP_NAME="myapp"
APP_DIR="/opt/myapp"
BACKUP_DIR="${APP_DIR}/backup"
DEPLOY_DIR="${APP_DIR}/deploy"

# 约定：
#   每次发布前先把当前版本备份到 backup/（文件名带时间戳）：
#     cp "${APP_DIR}/myapp.jar" "${BACKUP_DIR}/myapp.jar.$(date +%Y%m%d%H%M%S)"
#   回滚时把最近一份备份还原：
latest_backup="$(ls -1t "${BACKUP_DIR}"/myapp.jar.* 2>/dev/null | head -1 || true)"
if [ -z "$latest_backup" ]; then
  echo "找不到备份，无法回滚（${BACKUP_DIR}/myapp.jar.* 不存在）"
  exit 1
fi
echo "回滚目标: $latest_backup"

cp "$latest_backup" "$DEPLOY_DIR/myapp.jar.new"
mv "$DEPLOY_DIR/myapp.jar.new" "$APP_DIR/myapp.jar"   # 先拷后移：避免半写坏文件

systemctl restart "$APP_NAME"
echo "回滚完成。检查: systemctl status $APP_NAME && journalctl -u $APP_NAME -f"
