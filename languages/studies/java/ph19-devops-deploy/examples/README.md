# ph19 DevOps 与部署 示例

> 七个示例目录对应主文档「3. 语法与参数」主线：systemd/Shell 部署基础（ex07）→ Spring Boot 打包与 jar 结构（ex02）→ Dockerfile + Compose（ex03）→ K8s 清单（ex04）→ Helm（ex05）→ GitHub Actions（ex06）；ex01 用纯 Java 演示贯穿全阶段的可观测三件套（健康检查 / JSON 结构化日志 / 优雅停机）。验证环境：**OpenJDK 17.0.18（Homebrew）**；pom 基线 Spring Boot 3.3.0 + Maven 3.9（与 ph14~ph18 同源）。

## 验证状态（重要，如实标注）

**本机（macOS）无 docker、无 mvn、无 helm/kubectl**：依赖它们的示例一律如实标注「未在本环境验证」/「未在本环境实际构建验证」，并给出可复现命令。**纯 Java 部分已在本机实测**：

- `ex01-healthcheck-logging`（纯 Java 17，JDK 自带 HttpServer）—— 已验证（OpenJDK 17.0.18 实测 6/6 PASS）
- `ex02` 的 `JarLayersInspector.java`（纯 Java 17，java.util.zip）—— 已验证（OpenJDK 17.0.18 实测：演示分层 jar 三层解析 + 普通 jar 诊断均正确）
- `ex07` 三个 shell 脚本 —— 语法已通过 `bash -n`（macOS bash 3.2）校验；面向 Linux systemd 的执行未在本环境验证

其余全部为配置/清单类交付物（写出来即交付物），标注「未在本环境实际构建验证」并给出验证命令。请不要假设本仓库替你在有 docker/kubectl/helm 的机器上跑过它们。

| 目录 | 主题 | 依赖 | 验证状态 |
|------|------|------|---------|
| ex01-healthcheck-logging/ | 健康检查端点（liveness/readiness 语义）+ JSON 结构化日志 + SIGTERM 优雅停机 | 无（纯 Java 17） | 已验证（OpenJDK 17.0.18 本机实测 6/6 PASS） |
| ex02-spring-boot-jar-packaging/ | Spring Boot 可执行 jar / 分层 jar 的 Maven 配置 + jar 结构检查工具 | pom：Boot 3.3（需 mvn）；工具：无 | pom/yml 未在本环境验证；JarLayersInspector 已验证 |
| ex03-dockerfile-compose/ | 多阶段 Dockerfile + Compose（Java+MySQL8+Redis7）+ init.sql + .dockerignore | docker / compose v2 | 未在本环境实际构建验证 |
| ex04-k8s-manifests/ | namespace/configmap/secret/deployment/service/hpa（三类探针 + 滚动 + preStop） | kubectl + 集群 | 未在本环境实际构建验证 |
| ex05-helm-chart/ | Chart.yaml / values / templates 全套 + values-prod | helm 3 | 未在本环境实际构建验证 |
| ex06-github-actions/ | .github/workflows/ci.yml：build→test→image→deploy | GitHub 仓库 | 未在本环境实际构建验证 |
| ex07-script-deploy/ | deploy.sh / health-check.sh / rollback.sh / myapp.service | Linux + systemd | bash -n 语法已校验；执行未在本环境验证 |

## 一条验证主链（无任何外部服务，推荐从这开始）

```bash
# 1. 纯 Java 可观测三件套（对应主文档 3.9/3.11）
cd ex01-healthcheck-logging
javac ex01-healthcheck-logging.java
java Ex01HealthcheckLoggingDemo        # 输出 6 行 PASS + JSON 日志 + 优雅停机过程

# 2. jar 结构检查器（对应主文档 3.2）
cd ../ex02-spring-boot-jar-packaging
javac JarLayersInspector.java
java JarLayersInspector <任意 jar 的路径>    # 无 mvn 时的构造演示命令见该目录 README
```

## 需要外部工具链的验证（未在本环境验证，命令可复现）

```bash
# ex02 打包（有 mvn 的环境）
cd ex02-spring-boot-jar-packaging && mvn -B clean package && java -jar target/myapp.jar

# ex03 镜像 + Compose（有 docker 的环境；先把 pom.xml/src 放进该目录或复用 project 工程）
cd ex03-dockerfile-compose
docker compose up -d --build
curl -fsS http://127.0.0.1:8080/actuator/health

# ex04/ex05（有 kubectl / helm 的环境）
cd ex04-k8s-manifests && kubectl apply --dry-run=client -f deployment.yaml
cd ../ex05-helm-chart && helm lint ./app-chart && helm template myapp ./app-chart -f app-chart/values-prod.yaml

# ex06（推到真实 GitHub 仓库观察 Actions；或装 nektos/act 本地试跑 build-test job）
```

## 示例速览与教学点

### ex01：健康检查 + 结构化日志 + 优雅停机（已验证）

零依赖演示「应用侧可观测最小三件套」：`/actuator/health` 探针协议、JSON 行日志（可检索字段）、SIGTERM 优雅停机（拒新 → 等在途 → 超时兜底）。自检覆盖探针语义分工（DB DOWN 时 readiness DOWN 但 liveness UP）。

### ex02：Spring Boot 打包配置 + jar 结构检查器（pom 未验证 / 工具已验证）

`pom.xml` 的 repackage + `<layers>` 开关、`application.yml` 的优雅停机与探针配置；`JarLayersInspector` 把「fat jar / layers.idx」变成肉眼可见的输出。

### ex03：Dockerfile + Compose（未在本环境实际构建验证）

多阶段构建、分层 COPY、非 root、HEALTHCHECK、`.dockerignore`；compose 用健康依赖串起 Java + MySQL + Redis，`mem_limit` 与 `MaxRAMPercentage=75` 配套。

### ex04：K8s 清单（未在本环境实际构建验证）

Deployment（滚动策略 + 三类探针 + resources + preStop）→ Service → ConfigMap/Secret → HPA，逐文件注释解释「为什么这样设计」；无集群也能 `dry-run=client` 静态校验。

### ex05：Helm Chart（未在本环境实际构建验证）

Chart 全套 + dev/prod 两套 values；`helm lint` / `helm template` 纯本地校验，`helm rollback` 给一键回滚。

### ex06：GitHub Actions（未在本环境实际构建验证）

三 Job 门禁：测试绿才推镜像（不可变 tag = Git SHA）、镜像推成才部署、deploy 走 environment 审批；密钥全走 Secrets。

### ex07：Shell 部署脚本集（bash -n 已校验）

systemd 档位的完整脚本集，`set -euo pipefail` + HTTP 探活 + 备份式回滚；README 末尾有「脚本做的事 vs K8s 里谁替你做」对照表。

## 清理

`*.class` 编译产物在 ex01/ex02 目录内生成，`rm -f *.class` 清理；其余示例无构建产物。仓库内所有示例均不产生 git 跟踪的编译产物。
