# project/springboot-deploy-template/Dockerfile
# 多阶段构建 + 非 root + HEALTHCHECK（对应主文档 3.3；逐行解释见 examples/ex03-dockerfile-compose/Dockerfile）
# 验证命令（有 docker 的环境，在此目录下执行）：
#   docker build -t myapp:dev .
#   docker run -d -p 8080:8080 -m 512m --name myapp myapp:dev
#   docker exec myapp whoami        # appuser
# 验证状态：未在本环境实际构建验证（本机无 docker）
FROM maven:3.9-eclipse-temurin-17 AS builder
WORKDIR /build
COPY pom.xml .
RUN mvn -B dependency:go-offline
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
