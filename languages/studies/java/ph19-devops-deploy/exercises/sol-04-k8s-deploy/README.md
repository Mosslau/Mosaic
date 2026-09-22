# exercises/sol-04-k8s-deploy/README.md

> 练习 4 参考实现：`deployment.yaml` + `service.yaml` + `configmap.yaml` + `secret.yaml` + `hpa.yaml`（对象与语义逐条对齐主文档 3.5/3.11/3.12，每份文件头注释写「答案要点」）。

## 验证命令（有 kubectl 的环境；未在本环境实际构建验证）

```bash
# 1. 先建命名空间（清单里 namespace: myapp 依赖它存在）
kubectl create namespace myapp
# 2. 按依赖顺序 apply
kubectl apply -f configmap.yaml -f secret.yaml -f deployment.yaml -f service.yaml -f hpa.yaml
# 3. 等滚动就绪（内部等 readinessProbe）
kubectl rollout status deployment/myapp -n myapp
# 4. 验证对象
kubectl get pods,svc,hpa -n myapp
# 5. 滚动发布与回滚（练习 4 验收的动作）
kubectl set image deployment/myapp myapp=myregistry/myapp:1.5.0 -n myapp
kubectl rollout undo deployment/myapp -n myapp
```

## 无集群的替代检查

```bash
kubectl apply --dry-run=client -f deployment.yaml    # 不需要集群的 schema 级静态校验
```

## 自检问题（对照答案要点）

- 探针为什么指向 `liveness`/`readiness` 两个**不同**的 actuator 端点而不是都指 `/actuator/health`？（提示：DB 故障应只摘流量不重启）
- `maxUnavailable: 0` 会造成滚动发布期间新老并存、总副本 ≥ 期望值——代价是什么？什么时候可以放宽？
- `preStop sleep 5` + `terminationGracePeriodSeconds: 40` 与 Spring 的 `server.shutdown: graceful` 三者的先后顺序？
