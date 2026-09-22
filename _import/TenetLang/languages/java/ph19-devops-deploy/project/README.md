# ph19 阶段项目：Spring Boot 部署模板

## 需求

roadmap「19. DevOps 与部署阶段」推荐项目之一——**Spring Boot 部署模板**：把本阶段练习 1~4 与全部 examples 的要点收进一套「复制即可用」的部署资产，覆盖一条 Java 服务从源码到生产的完整交付链：

**打包（可执行 jar）→ 镜像（Dockerfile 多阶段）→ 单机编排（Compose 起 Java+MySQL+Redis）→ 集群声明式部署（K8s 清单）→ 持续交付（GitHub Actions）→ 可观测（健康检查/优雅停机/结构化日志）**

> 生产路径的完整验收需要 docker/kubectl（本机没有）；因此模板另配一个**纯 Java 参考实现**（`purejava/`）：用 JDK 自带能力模拟「Boot 可执行 jar + actuator 健康端点 + 配置外置 + SIGTERM 优雅停机」的语义，配冒烟脚本 `app-smoke.sh`，**只靠 javac/java 就能验收「打包 → 探活 → 优雅停机」这条部署主链**（已在 OpenJDK 17.0.18 本机验证）。

## 目录结构

```
project/
├── README.md
└── springboot-deploy-template/
    ├── pom.xml                        # 真实 Boot 3.3 工程：打包可执行 jar + 分层（未验证：需 mvn）
    ├── Dockerfile                     # 多阶段 + 非 root + HEALTHCHECK（未在本环境实际构建验证）
    ├── .dockerignore
    ├── docker-compose.yml             # app + mysql8 + redis7 一键编排（未在本环境实际构建验证）
    ├── .github/workflows/ci.yml       # build → test → image → deploy 流水线（未在本环境实际构建验证）
    ├── deploy/
    │   └── k8s/                       # namespace/configmap/secret/deployment/service/hpa
    │       ├── namespace.yaml         #   （与 examples/ex04 同源，逐文件注释见其 README）
    │       ├── configmap.yaml
    │       ├── secret.yaml
    │       ├── deployment.yaml
    │       ├── service.yaml
    │       └── hpa.yaml
    ├── src/main/java/com/example/myapp/      # 真实 Boot 应用（Application + PingController）
    │   ├── MyappApplication.java
    │   └── web/PingController.java
    ├── src/main/resources/application.yml    # 优雅停机 / 探针端点 / prometheus 暴露
    ├── purejava/                             # 纯 Java 参考实现（已验证，见下）
    │   ├── src/purejava/MiniApp.java         #   可执行 jar 形态的迷你服务
    │   └── app-smoke.sh                      #   冒烟自检：打包 → 启动 → 探活 → 优雅停机
    └── README.md                             # 模板使用说明与验证命令
```

## 功能清单

- [x] **真实工程打包配置**：`pom.xml` 打可执行 fat jar（`java -jar`）并开启分层（`BOOT-INF/layers.idx`）
- [x] **可复现镜像**：`Dockerfile` 多阶段构建、非 root 运行、HEALTHCHECK、`-XX:MaxRAMPercentage=75`
- [x] **单机编排**：`docker-compose.yml` 健康依赖串起 app + MySQL 8 + Redis 7，数据卷 + init SQL
- [x] **集群清单**：`deploy/k8s/` Deployment（滚动 + 三类探针 + preStop）、Service、ConfigMap/Secret、HPA
- [x] **CI/CD**：`.github/workflows/ci.yml` build → test → image（GHCR 不可变 tag）→ deploy（helm/rollout 语义，environment 门禁）
- [x] **可观测配置**：`application.yml` 开优雅停机、liveness/readiness 探针端点、prometheus 指标端点
- [x] **纯 Java 可测的部署主链**：`purejava/` 用 javac/java 真实验收「打包成可执行 jar → 启动 → HTTP 探活 → 外置配置注入 → SIGTERM 优雅停机」

## 验证状态（如实标注）

| 部分 | 状态 | 验证环境 |
|------|------|---------|
| `purejava/` 冒烟链（javac/java/curl/kill） | **已验证**：app-smoke.sh 全部 PASS | OpenJDK 17.0.18（Homebrew）+ macOS |
| `pom.xml` 打包 / `application.yml` 运行 | 未在本环境验证（需 mvn + Boot 依赖） | Maven 3.9 + OpenJDK 17 |
| `Dockerfile` 构建 / `docker-compose.yml` 编排 | 未在本环境实际构建验证 | Docker 24+ |
| `deploy/k8s/*` 应用 | 未在本环境实际构建验证（可用 `kubectl apply --dry-run=client` 静态校验） | kubectl + 集群 |
| `.github/workflows/ci.yml` | 未在本环境实际构建验证（需真实 GitHub 仓库） | GitHub Actions runner |

## 验收标准

**验收 1（纯 Java 冒烟，本机已通过）**：在 `purejava/` 执行 `./app-smoke.sh`，输出含逐条 PASS：

- 能打出可执行 jar 且 `java -jar` 直接运行（不用 classpath）
- `/actuator/health` 返回 UP、`/ping` 返回运行配置（默认 profile=dev）
- 用 `-Dapp.profile=prod` 覆盖后 `/ping` 读到 prod（配置外置于代码之外注入）
- `kill -TERM` 后进程优雅退出，日志含 `shutdown_complete`（存量逻辑先收尾）

**验收 2（真实工程路径，需对应工具链）**：docker 路径——`docker compose up -d --build` 后三服务 healthy、`curl /actuator/health` UP、`docker compose stop mysql` 后 readiness 转 DOWN 且 app 不退出；k8s 路径——`kubectl apply -f deploy/k8s/` 后 rollout 完成、`kubectl rollout undo` 可回滚；CI 路径——push 到 GitHub 后流水线绿、镜像 tag 为 Git SHA。

## 扩展方向

- **接真数据源**：把 `purejava` 换成真 Boot 工程接 MySQL/Redis（pom 已含 actuator/prometheus，DB/Redis starter 按 ph13/ph18 的坐标加）——连接串走 compose 环境变量 / k8s ConfigMap（模板已接线）
- **Helm 化**：`deploy/k8s/` 的清单模板化 + 多环境 values 复用 [`examples/ex05-helm-chart`](../examples/ex05-helm-chart/) 的 Chart，流水线 deploy 步骤即可用 `helm upgrade`（主文档 3.6/3.8）
- **灰度发布**：金丝雀权重 / Argo Rollouts（主文档 3.12）——模板的滚动更新是默认档，进阶策略在指标与流量控制器上做
- **ph18 秒杀 demo 上生产**：按主文档 5 章的「上生产路径」，把 ph18 project 的三个模拟后端换成真中间件后用本模板部署
