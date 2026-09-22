# examples/ex05 —— Helm Chart

> 对应主文档 [3.6 Helm 打包](../../19-devops-deploy.md)。把 ex04 的手工清单模板化成 Chart：同一份模板 + `values.yaml`（默认）与 `values-prod.yaml`（覆盖）即可渲染 dev/prod 两套清单，且 `helm upgrade` 自带版本历史与一键回滚。

## 目录结构

```
ex05-helm-chart/
├── README.md
└── app-chart/
    ├── Chart.yaml            # 元数据（name/version/appVersion）
    ├── values.yaml           # 默认参数（replica/image/probes/resources/config/secret 全部集中）
    ├── values-prod.yaml      # 生产覆盖（只写与默认不同的键）
    └── templates/
        ├── _helpers.tpl      # 命名/label 复用模板
        ├── deployment.yaml   # Deployment：参数注入 replicas/image/探针/resources/preStop
        ├── service.yaml      # Service
        ├── configmap.yaml    # 非敏感配置（values.config 循环生成）
        └── secret.yaml       # 敏感配置（values.secret；生产用外部 Secret 方案）
```

## 验证命令（有 helm 的环境；未在本环境实际构建验证：本机无 helm）

```bash
# 1. lint：静态检查 Chart 结构/模板语法（本地执行，不碰集群）
helm lint ./app-chart
# 2. 本地渲染：把模板+values 展开成最终 YAML，人肉 review 或管道给 kubectl dry-run
helm template myapp ./app-chart -f app-chart/values-prod.yaml
# 3. 安装/升级（release 名 myapp 记录在集群，之后能回滚）
helm install myapp ./app-chart --namespace myapp --create-namespace --set image.tag=1.4.2
# 4. 发布新版本（GitHub Actions 流水线的 deploy 步骤就是这一行，见 ex06）
helm upgrade myapp ./app-chart --namespace myapp --set image.tag=1.5.0
# 5. 出问题回滚到上一个 release（3.12 的「一键回滚」）
helm rollback myapp 1
# 6. 查看 release 历史与当前值
helm history myapp
helm get values myapp
```

## 教学点速查

- **Helm 解决手工清单的三个痛点**（主文档 3.6）：环境差异（values 覆盖）、参数散落（全进 values）、无法回滚（release 版本历史）。
- **渲染是纯本地动作**：`helm template`/`lint` 不需要集群——流水线里可先渲染再 `kubectl apply` 或直接 `helm upgrade`。
- **release 名做资源前缀**：`_helpers.tpl` 用 `Release.Name + Chart.Name` 拼资源名，同一套 Chart 能在同一集群部署多套互不冲突（如 blue/green）。
- **values 里放 secret 只适合教学**：生产把 `secret.yaml` 模板删掉，改用 External Secrets / Vault 注入，防止密钥进 git。
