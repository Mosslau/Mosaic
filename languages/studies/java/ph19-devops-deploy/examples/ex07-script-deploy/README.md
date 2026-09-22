# examples/ex07 —— Shell 部署脚本集（裸 jar + systemd 档位）

> 对应主文档 [3.1 Linux/Shell 部署基础](../../19-devops-deploy.md)。当服务规模不需要容器时（单机小服务、批处理、还没到多实例），systemd + 脚本是最低运维成本的部署形态。K8s 把「崩溃重启/健康检查/回滚」做成了平台能力，本目录的脚本是同一套语义在 systemd 世界的显式实现——看懂它，K8s 清单的每一项都有了「它在替你做哪个人肉动作」的参照。

## 文件清单

| 文件 | 作用 | 验证状态 |
|------|------|---------|
| `deploy.sh` | 服务生命周期：start/stop/restart/status/logs + 安装 systemd unit；HTTP 探活 + 90s 等待窗口 | 语法已通过本机 bash -n 校验；实际执行需 Linux systemd，未在本环境验证 |
| `health-check.sh` | 独立探活脚本：进程 + HTTP 双层检查，且解析 body 的 `status` 字段（不只盯 HTTP 码） | 同上 |
| `rollback.sh` | 版本回退：备份 → 还原 → systemctl restart（3.12 的「可回滚」在 systemd 世界的形态） | 同上 |
| `myapp.service` | systemd unit：低权限用户、Restart=on-failure、TimeoutStopSec 配优雅停机 | 未在本环境实际验证（需 Linux） |

## 验证命令

```bash
# 本机（macOS）能做的：bash 语法校验（本仓库已执行并通过）
bash -n deploy.sh && bash -n health-check.sh && bash -n rollback.sh && echo "syntax OK"
# chmod + 实际部署（Linux 上）
chmod +x deploy.sh health-check.sh rollback.sh
sudo ./deploy.sh install-unit        # 装 unit 并开机自启
./deploy.sh start                    # 启动 + 探活等待
./deploy.sh status
./deploy.sh logs 50
# 故障演练：curl 打 DOWN 后跑 health-check.sh 观察其失败路径
```

## 教学点速查

- **`set -euo pipefail` 是脚本安全默认**：任何脚本第一行都该有——错误静默吞掉是运维事故的最大来源。
- **探活看「服务可用」不看「进程活着」**：`systemctl is-active` + HTTP health 双层检查；health-check.sh 还解析 body 的 status，避免「200 但 DOWN」的假阳性（呼应 3.5 readiness 语义）。
- **优雅停机靠 SIGTERM 时序**：`systemctl stop` 默认发 SIGTERM，Spring 的 `server.shutdown=graceful` 收尾存量请求，`TimeoutStopSec=30` 兜底超时（3.11）。
- **回滚前提是留备份**：发布前备份当前版本是「发布必须可回滚」的最朴素实现（3.12）——容器世界的不可变 tag 也是同一思想。

## 与容器/K8s 档位的对应

| 脚本做的事 | K8s 里谁替你做 |
|-----------|---------------|
| Restart=on-failure | livenessProbe 失败 → kubelet 重启容器 |
| HTTP 探活等待 90s | startupProbe/readinessProbe |
| rollback.sh 还原备份 | kubectl rollout undo / helm rollback |
| systemctl enable | DaemonSet/static pod（随节点起） |
