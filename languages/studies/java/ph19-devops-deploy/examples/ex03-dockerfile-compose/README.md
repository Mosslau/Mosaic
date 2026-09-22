# examples/ex03 —— Dockerfile + Docker Compose 配置集

> 对应主文档 [3.3 Dockerfile 最佳实践](../../19-devops-deploy.md) 与 [3.4 Docker Compose 编排](../../19-devops-deploy.md)。本目录是「单机把 Java + MySQL + Redis 一键起起来」的完整配置。

## 文件清单

| 文件 | 作用 | 验证状态 |
|------|------|---------|
| `Dockerfile` | 多阶段构建（maven 编译 → temurin-17-jre 运行）、分层 jar 说明、非 root、HEALTHCHECK、`MaxRAMPercentage=75` | 未在本环境实际构建验证（无 docker） |
| `docker-compose.yml` | app(mysql/redis 健康依赖 + 环境变量注入 + 端口) + mysql(命名卷 + init.sql) + redis | 未在本环境实际构建验证（无 docker） |
| `.dockerignore` | 构建上下文过滤（.git/target/class） | 无需运行 |
| `init.sql` | MySQL 首次启动建表 + 演示数据 | 未在本环境实际验证（需 docker 起 MySQL） |

> 需要 `pom.xml` + `src/` 才能 `docker compose up -d --build`（builder 阶段要编译）。直接复用 [`project/springboot-deploy-template/`](../../project/springboot-deploy-template/) 的工程：把本目录四个文件放进该工程目录后执行下方命令。

## 验证命令（有 docker 的环境）

```bash
# 1. 起全套（先构建镜像，再按依赖顺序拉起 mysql → redis → app）
docker compose up -d --build
# 2. 看健康状态（app 变 healthy 才算整套就绪）
docker compose ps
# 3. 探活（Dockerfile 的 HEALTHCHECK 与 K8s 探针吃同一个端点）
curl -fsS http://127.0.0.1:8080/actuator/health
# 4. 看日志（容器日志进 stdout，docker logs 即查看方式——应用不该写文件日志）
docker compose logs -f app
# 5. 模拟故障：停掉 MySQL，观察 app 的 readiness 探活结果（配置只在 readiness 体现，进程不重启）
docker compose stop mysql && curl -s http://127.0.0.1:8080/actuator/health/readiness
# 6. 收尾（-v 会连数据卷一起删，慎用）
docker compose down        # 保留数据卷
docker compose down -v     # 连数据一起清空（重做实验用）
```

## 教学点

- **健康依赖是 compose 的灵魂**：`depends_on` 不带 `condition: service_healthy` 时只保证「容器起了」，MySQL 还在初始化应用就连库失败——这是「容器启动 ≠ 服务就绪」的第一课（主文档 3.4）。
- **服务名即 DNS**：app 里连 `mysql:3306` 不是 `localhost:3306`——每个容器有自己的网络命名空间（主文档 4.1）。
- **mem_limit 必须和 `-XX:MaxRAMPercentage` 配套**：容器内存是「硬墙」，JVM 参数决定墙内怎么分（主文档 4.4）。
- **数据只能进卷**：MySQL/Redis 的数据目录都挂命名卷，容器重建不丢数据；`init.sql` 只在数据卷为空时执行一次。

## 进阶：加 Prometheus 抓取（对应主文档 3.10）

把下面这段加进 `docker-compose.yml` 的 `services:` 下，即可用 Prometheus 抓 app 的指标（`prom/prometheus` 镜像启动时挂载你的 `prometheus.yml`）：

```yaml
  prometheus:
    image: prom/prometheus:v2.53.0
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"
```

`prometheus.yml` 的抓取片段见主文档 3.10，target 指向 `app:8080`（compose 网络内服务名解析）。
