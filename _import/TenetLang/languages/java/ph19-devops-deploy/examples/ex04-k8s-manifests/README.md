# examples/ex04 —— Kubernetes 部署清单

> 对应主文档 [3.5 Kubernetes 核心概念与部署清单](../../19-devops-deploy.md) 与 [3.11 健康检查与优雅停机](../../19-devops-deploy.md)。一套「java 服务上 K8s」的最小但完整清单，文件按 apply 顺序编号。

## 文件清单（均未在本环境实际构建验证：本机无 kubectl/集群）

| 文件 | 作用 | 依赖对象 |
|------|------|---------|
| `namespace.yaml` | 命名空间 `myapp`（环境隔离） | — |
| `configmap.yaml` | 非敏感环境配置（DB_URL/日志级别等），envFrom 注入 | namespace |
| `secret.yaml` | 敏感配置（DB/Redis 密码），envFrom 注入 | namespace |
| `deployment.yaml` | 2 副本 + 滚动更新 + 三类探针 + 资源上限 + preStop | configmap / secret |
| `service.yaml` | ClusterIP 稳定入口（selector 接住 Deployment 的 Pod） | deployment |
| `hpa.yaml` | CPU 超 60% 扩到最多 8 副本 | deployment（需 metrics-server） |

## 验证命令（有 kubectl 的环境）

```bash
# 1. 一键 apply（顺序即依赖序：ns → config/secret → deploy → svc → hpa）
kubectl apply -f namespace.yaml -f configmap.yaml -f secret.yaml \
              -f deployment.yaml -f service.yaml -f hpa.yaml
# 2. 看滚动发布是否就绪（内部在等 readinessProbe 通过）
kubectl rollout status deployment/myapp -n myapp
# 3. 看 Pod/Service/HPA
kubectl get pods,svc,hpa -n myapp
# 4. 从集群内探活（用一次性 curl Pod 打 Service 名）
kubectl run -it --rm probe --image=curlimages/curl -n myapp -- \
  curl -fsS http://myapp/actuator/health
# 5. 演示滚动发布 + 回滚（3.12）
kubectl set image deployment/myapp myapp=myregistry/myapp:1.5.0 -n myapp
kubectl rollout status deployment/myapp -n myapp
kubectl rollout undo deployment/myapp -n myapp          # 回滚到上一个 revision
kubectl rollout history deployment/myapp -n myapp       # 看历史 revision
```

**无集群也能做的静态校验**（写错字段名/缩进时 `dry-run=client` 只做本地 schema 检查）：

```bash
kubectl apply --dry-run=client -f deployment.yaml -n myapp
```

## 教学点速查

- **三类探针的语义不能混**（主文档 3.5/3.11）：DB 抖动 → readiness DOWN 摘流量（不杀）；死锁 → liveness 杀容器重启；慢启动 → startupProbe 兜底 60s。
- **`resources` 与镜像里的 `-XX:MaxRAMPercentage=75` 成对出现**：`limits.memory` 是容器的墙，JVM 参数决定墙内怎么分堆（主文档 4.4）。
- **不可变 image tag（`1.4.2` 而非 `latest`）是回滚的前提**：`rollout undo` 要能精确回到「某个确定版本」（主文档 3.3/3.12）。
- **Secret 的 base64 只是编码**：本仓库示例用明文便于教学，生产请用外部 Secret 方案，别把明文密钥提交进 git。

## 进阶方向

- 外部流量接入：加 Ingress 资源（controller 承担 3.7 Nginx 的职责）。
- 参数化：同一套清单在 dev/prod 复用靠 Helm —— 见 [`../ex05-helm-chart/`](../ex05-helm-chart/)。
- 金丝雀权重发布：Argo Rollouts / Istio（主文档 3.12 概念性提及）。
