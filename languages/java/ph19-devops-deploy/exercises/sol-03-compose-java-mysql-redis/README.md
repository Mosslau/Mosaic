# exercises/sol-03-compose-java-mysql-redis/README.md

> 练习 3 的参考实现。本目录只有编排文件（`docker-compose.yml`），app 服务构建所需的工程文件请复用相邻参考实现：

| app 工程需要 | 来源 |
|-------------|------|
| `pom.xml`（打包 + 依赖 web/actuator/prometheus） | [`../sol-01-spring-boot-packaging/pom.xml`](../sol-01-spring-boot-packaging/pom.xml) |
| `src/main/java/.../MyappApplication.java`（@SpringBootApplication 主类） | 任意极简 Boot 主类即可（project/ 有完整版） |
| `src/main/resources/application.yml`（优雅停机 + 探针端点） | [`../sol-01-spring-boot-packaging/src/main/resources/application.yml`](../sol-01-spring-boot-packaging/src/main/resources/application.yml) |
| `Dockerfile`（多阶段 + 非 root + HEALTHCHECK） | [`../sol-02-docker-deploy/Dockerfile`](../sol-02-docker-deploy/Dockerfile) |
| `init.sql`（演示建表，MySQL 首次启动执行） | 见本目录下同款示例 `../../examples/ex03-dockerfile-compose/init.sql` |

把上述文件与 `docker-compose.yml` 放进同一目录后执行该文件头注释里的验证命令。

**练习 3 的验收自测（故障演练）**：`docker compose stop mysql` 后访问 `/actuator/health/readiness` 应转 DOWN（Boot 的 db health indicator 挂到 readiness），而 app 进程不退出、`docker compose ps` 里 app 因 healthcheck 失败显示 unhealthy 但不会被重启——与 K8s 的「readiness 摘流量、liveness 才杀」语义一致（主文档 3.5/3.11）。

验证状态：未在本环境实际构建验证（本机无 docker）。
