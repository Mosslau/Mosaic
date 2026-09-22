# exercises/sol-02-docker-deploy/Dockerfile —— 练习 2 参考实现（对应主文档 3.3）
# 答案要点：
#   1. 多阶段：builder 有 JDK+maven（编译），runtime 只有 JRE（运行）→ 镜像小、无源码无构建工具
#   2. 非 root：useradd 后 USER appuser
#   3. HEALTHCHECK 探测 /actuator/health（K8s 环境用探针，compose/docker run 用它）
#   4. ENTRYPOINT 写 -XX:MaxRAMPercentage=75.0：配合容器内存限制按比例划堆（主文档 4.4），不写死 -Xmx
#   5. 层缓存意识：先 COPY pom.xml 拉依赖、后 COPY src（见下方注释）
# 验证命令（有 docker 的环境，把 pom.xml/src 放同目录）：
#   docker build -t myapp:dev .
#   docker run -d --rm -p 8080:8080 -m 512m --name myapp myapp:dev
#   docker inspect --format '{{.State.Health.Status}}' myapp     # healthy 即通过
#   docker exec myapp whoami                                     # appuser（非 root）
#   docker logs myapp
# 验证状态：未在本环境实际构建验证（本机无 docker）
FROM maven:3.9-eclipse-temurin-17 AS builder
WORKDIR /build
COPY pom.xml .
RUN mvn -B dependency:go-offline        # 依赖层缓存：pom 不变这层不重跑
COPY src ./src
RUN mvn -B -DskipTests package

FROM eclipse-temurin:17-jre
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=builder /build/target/myapp.jar /app/myapp.jar
USER appuser
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=40s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8080/actuator/health || exit 1

ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75.0", "-jar", "/app/myapp.jar"]
