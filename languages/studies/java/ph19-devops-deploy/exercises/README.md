# ph19 DevOps 与部署 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> **与 roadmap「19. DevOps 与部署阶段」练习小节的对应**：四题一一对应 roadmap 列的四个练习——练习 1 = Spring Boot 打包、练习 2 = Docker 部署、练习 3 = Compose 启动 Java + MySQL + Redis、练习 4 = Kubernetes 部署。四题是「服务上生产」的一条技能线：把工程打成可部署 jar（1）→ 打成可复现镜像（2）→ 把镜像和依赖一键编排起来（3）→ 交给集群声明式发布（4）。
> **验证纪律（与本机工具链匹配）**：练习 1~4 的完整执行分别需要 mvn / docker / docker compose / kubectl——本机（macOS）没有这些工具，所以**每一题都按「在有该工具链的机器上如何验收」给出命令**，参考实现（sol-*）附带「无工具链时能做什么」的替代检查（如练习 1 用 ex02 的 JarLayersInspector 检查 jar 结构、练习 4 用 `kubectl apply --dry-run=client` 静态校验）。凡未在本机实际执行的步骤一律如实标注「未在本环境验证」。

四题参考实现与生产能力的映射速查：

| 练习 | 参考实现 | 生产落地点（主文档） | examples 参照 |
|------|---------|---------------------|------|
| 1 Spring Boot 打包 | sol-01（pom.xml + 结构检查命令） | 可执行 jar / 分层 jar（3.2）、配置外置（3.2） | ex02 |
| 2 Docker 部署 | sol-02（Dockerfile） | 多阶段/非 root/HEALTHCHECK/不可变镜像（3.3） | ex03 |
| 3 Compose 起 Java+MySQL+Redis | sol-03（docker-compose.yml + application.yml） | 健康依赖/服务名即 DNS/数据卷（3.4） | ex03 |
| 4 Kubernetes 部署 | sol-04（deployment/service/configmap） | 探针语义/滚动更新/配置分离（3.5/3.11/3.12） | ex04 |

## 练习 1：Spring Boot 打包（★★）

**目标**：把 Maven 工程打成「一个命令就能跑」的可执行 jar，并理解分层 jar 对镜像构建的意义。
**要求**：
- 基于 Spring Boot 3.3 + Java 17 写一个 `pom.xml`：能打出可执行 fat jar（`java -jar` 直接运行），且开启分层（产物含 `BOOT-INF/layers.idx`）
- 给一个部署用 `application.yml`：开启优雅停机（`server.shutdown: graceful`）、暴露 health/prometheus 端点、开启 liveness/readiness 探针端点
- 能说出可执行 jar 里 `BOOT-INF/lib`、`org/springframework/boot/loader`、MANIFEST 的 `Main-Class`/`Start-Class` 各是什么、为什么 `mvn package` 的普通 jar 不能直接 `java -jar`

**验收**（有 mvn 的环境）：`mvn clean package` 后 `java -jar target/*.jar` 能起服务并访问 `/actuator/health` 返回 UP；jar 内含 `BOOT-INF/layers.idx`（可用 `unzip -l` 验证，或用 examples/ex02 的 `JarLayersInspector` 检查）。
**无 mvn 的替代检查**：写出的 pom.xml 与 examples/ex02 对照 diff；用 ex02 的 inspector 工具手工构造分层 jar 跑通解析。参考实现见 `sol-01-spring-boot-packaging/`。

## 练习 2：Docker 部署（★★）

**目标**：写一份生产质量的 Dockerfile，把 Java 服务打成可复现镜像。
**要求**：
- 多阶段构建：builder 阶段用 maven 镜像编译，runtime 阶段用 JRE 镜像运行（JDK 不残留、源码不残留）
- 运行时用非 root 用户
- 加 HEALTHCHECK，探测 `/actuator/health`
- 启动命令写 JVM 容器内存参数（`-XX:MaxRAMPercentage`），并解释为什么配容器 `mem_limit`/`resources.limits.memory` 时必须用它而不是写死 `-Xmx`
- 配一份 `.dockerignore`（至少忽略 target/、.git）
- 能说出「不可变镜像 tag」为什么是回滚的前提

**验收**（有 docker 的环境）：`docker build -t <你选的名字> .` 成功；`docker run -m 512m -p 8080:8080 <镜像>` 后 healthcheck 变 healthy、进程以非 root 运行（`docker exec <容器> whoami`）；改一行代码重 build 时除 application 层外的层命中缓存。
参考实现见 `sol-02-docker-deploy/`。

## 练习 3：Compose 启动 Java + MySQL + Redis（★★★）

**目标**：用一份 Compose 文件把「应用 + 两个依赖中间件」按正确顺序一键拉起。
**要求**：
- 定义三个服务：app（本地 Dockerfile 构建）、mysql（8.0）、redis（7-alpine）
- mysql/redis 各配 healthcheck；app 用 `depends_on` + `condition: service_healthy` 等中间件真就绪才启动
- mysql 数据挂命名卷；首次启动自动执行一份建表 SQL（挂官方约定的 initdb 目录）
- app 通过环境变量注入数据库/Redis 连接信息——连接串里用的是**服务名**而不是 localhost，并解释原因
- app 加 `mem_limit`，并说明与 Dockerfile 里 `MaxRAMPercentage` 的关系

**验收**（有 docker 的环境）：`docker compose up -d --build` 后 `docker compose ps` 三服务均 healthy；`curl http://127.0.0.1:8080/actuator/health` UP；`docker compose stop mysql` 后 app 的 readiness 探活转 DOWN（但进程不退出）；重启后 mysql 数据仍在。
参考实现见 `sol-03-compose-java-mysql-redis/`。

## 练习 4：Kubernetes 部署（★★★）

**目标**：把 Java 服务写成 K8s 声明式清单：可自愈、可滚动发布、可回滚、可扩缩容。
**要求**：
- Deployment：2 副本 + 滚动更新（`maxUnavailable: 0`）+ 三类探针（startup 指向 liveness 路径并给足 JVM 启动宽限、readiness 指向 `/actuator/health/readiness`、liveness 指向 `/actuator/health/liveness`）+ `resources`（requests/limits）
- Service：ClusterIP，selector 与 Deployment 的 label 对应
- ConfigMap 放非敏感配置、Secret 放密码，注入方式为 envFrom
- 解释为什么探针路径要用 actuator 的 liveness/readiness 两个独立端点、以及「DB 抖动只该影响 readiness 不影响 liveness」
- HPA：CPU 平均利用率触发扩缩
- 解释 `preStop` + `terminationGracePeriodSeconds` 与 Spring 优雅停机如何配合成零停机发布

**验收**（有 kubectl + 集群的环境）：`kubectl apply -f .` 后 `kubectl rollout status deployment/myapp` 完成；`kubectl get pods,svc,hpa` 正常；`kubectl set image ...` 触发滚动、`kubectl rollout undo` 回滚成功。
**无集群的替代检查**：`kubectl apply --dry-run=client -f <file>` 静态校验全部清单通过。参考实现见 `sol-04-k8s-deploy/`。

## 完成后

做完四题继续到 [`project/`](../project/)：Spring Boot 部署模板把练习 1~4 的零件（打包配置、Dockerfile、compose、k8s 清单）外加 GitHub Actions 流水线收进一套「复制即可用」的部署资产。
