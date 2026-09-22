# examples/ex06 —— GitHub Actions 流水线

> 对应主文档 [3.8 CI/CD](../../19-devops-deploy.md)。完整文件是 `.github/workflows/ci.yml`（放在你自己的仓库根目录的 `.github/workflows/` 下即生效）。

## 文件清单

| 文件 | 作用 | 验证状态 |
|------|------|---------|
| `.github/workflows/ci.yml` | 三 Job 流水线：build-test → build-image（GHCR 不可变 tag）→ deploy（helm upgrade + rollout 等待） | 未在本环境实际构建验证（需真实 GitHub 仓库 / 托管 runner） |

## 验证方式

```bash
# 1. 把 ci.yml 放进自己仓库的 .github/workflows/，推到 GitHub 即触发
# 2. 本地近似验证（可选）：安装 nektos/act 后
#    act -j build-test
# 3. 关键前提
#    - 仓库需要 Maven 工程（pom.xml 在根目录，产物 finalName=myapp → target/myapp.jar）
#    - deploy Job 需要两个 Secret：KUBECONFIG（集群凭据文件内容）、GITHUB_TOKEN（自动注入，无需手配）
#    - deploy/app-chart 是 Helm Chart（复制 ex05 的 app-chart 到仓库 deploy/ 目录）
```

## 教学点速查（对应主文档 3.8）

- **Job 之间是门禁不是接力**：`needs` 保证上游绿了才轮到自己；三个 Job 失败互不牵连、日志分区可查。
- **产物传递**：jar 走 `upload-artifact`/重新构建而非「把工作区传下去」——每个 Job 都是干净的 runner，重新 `mvn package` 保证产物可复现。
- **不可变镜像 tag = Git SHA**：CI 部署的就是代码评审通过的那个提交；`rollout undo` 能精确退回（3.3/3.12）。
- **`environment: prod` + 人工审批**：生产发布默认要人点一下，杜绝「push 即上线」事故。
- **密钥只在运行时注入**：KUBECONFIG、Docker 凭据全部走 `secrets.*`，仓库里找不到任何明文。
