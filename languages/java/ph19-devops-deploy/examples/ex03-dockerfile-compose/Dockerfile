# examples/ex03-dockerfile-compose/Dockerfile
# Java 服务多阶段构建镜像（对应主文档 3.3 全部最佳实践：多阶段 / 分层 COPY / 非 root / HEALTHCHECK）
# 基线：eclipse-temurin 17（与学习基线一致）；构建环境 maven:3.9-eclipse-temurin-17
# 验证环境：Docker 24+（需联网拉基础镜像与 Maven 依赖）
# 验证命令（有 docker 的环境，在 examples/ex03-dockerfile-compose/ 目录下执行）：
#   docker build -t myapp:dev .                          # 构建
#   docker run --rm -p 8080:8080 -m 512m myapp:dev       # 运行（-m 512m 与 MaxRAMPercentage=75 配套，见主文档 4.4）
#   curl -fsS http://127.0.0.1:8080/actuator/health      # 探活
#   docker logs -f <container>                           # 看日志
# 验证状态：未在本环境实际构建验证（本机无 docker；多阶段构建/镜像运行需在有 docker 的机器执行）

# ---- 阶段一：builder，只负责编译，产物不进入运行镜像 ----
FROM maven:3.9-eclipse-temurin-17 AS builder
WORKDIR /build
# 先 COPY pom.xml 并预拉依赖：pom.xml 不变时这一层命中构建缓存，日常改代码不重下依赖
COPY pom.xml .
RUN mvn -B dependency:go-offline
# 再 COPY 源码并打包（-DskipTests：测试在 CI 的 build-test Job 跑，镜像构建不复测）
COPY src ./src
RUN mvn -B -DskipTests package

# ---- 阶段二：runtime，只装运行需要的最小集 ----
FROM eclipse-temurin:17-jre
# 装 curl 供 HEALTHCHECK / 手动探活用（K8s 环境用探针 httpGet 就不需要它，可按平台裁剪）
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
# 非 root 运行：独立低权限用户，进程被攻破时权限被限制
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app

# 分层 jar 从 builder 阶段拷出。只 COPY 最终 jar（每层一条 COPY 的进阶版见下方「分层 COPY」注释）
COPY --from=builder /build/target/myapp.jar /app/myapp.jar

USER appuser
EXPOSE 8080

# docker/compose 层的容器内自检：K8s 不依赖它（K8s 用自己的三类探针 httpGet 同一端点）
HEALTHCHECK --interval=10s --timeout=3s --start-period=40s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8080/actuator/health || exit 1

# 启动命令钉进镜像：MaxRAMPercentage=75 让 JVM 按容器内存上限按比例划堆（主文档 4.4）
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75.0", "-jar", "/app/myapp.jar"]

# ── 进阶：真正利用层缓存的「分层 COPY」（有 mvn 的环境可替换上面两行）────────────────────────
#   在 builder 阶段追加：
#     RUN java -Djarmode=layertools -jar /build/target/myapp.jar extract   # 把 fat jar 解成分层目录
#   并把 COPY --from=builder 替换为按层拷贝（依赖层 / loader 层几乎不变 → 命中 Docker 构建缓存）：
#     COPY --from=builder /build/dependencies/ ./
#     COPY --from=builder /build/spring-boot-loader/ ./
#     COPY --from=builder /build/snapshot-dependencies/ ./
#     COPY --from=builder /build/application/ ./
#   顺序不能乱：常变的 application 层永远最后拷（见主文档 3.3 表「分层 jar + 依赖层先 COPY」）

