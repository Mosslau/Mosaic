# springboot-deploy-template —— Spring Boot 部署模板使用说明

本目录是 ph19 综合项目的**真实部署资产**（总览、验收标准见上级 [`README.md`](../README.md)）。两条使用路径：

## 路径 A：本机纯 Java 冒烟（已验证，无需任何外部工具）

部署主链的语义验证在 `purejava/`，只依赖 JDK 17 + curl：

```bash
cd purejava
./app-smoke.sh     # 或 JAVA_HOME=/opt/homebrew/opt/openjdk@17 ./app-smoke.sh
```

输出逐条 PASS：可执行 jar 直接运行 → health 探活 → 默认/注入 profile → SIGTERM 优雅停机。

## 路径 B：真实工程路径（未在本环境验证，各步给出验证命令）

| 步骤 | 操作 | 验证命令（对应工具链） |
|------|------|----------------------|
| 1 打包 | 工程根执行 `mvn -B clean package`（产出 `target/myapp.jar`） | `java -jar target/myapp.jar`，curl `/actuator/health` |
| 2 镜像 | `docker build -t myapp:dev .` | `docker run -d -p 8080:8080 -m 512m myapp:dev`，`docker exec <容器> whoami` |
| 3 Compose | `docker compose up -d --build` | `docker compose ps` 三服务 healthy；`docker compose stop mysql` 观察 readiness 转 DOWN |
| 4 K8s | `kubectl apply -f deploy/k8s/`（先建 namespace） | `kubectl rollout status deployment/myapp -n myapp`；`kubectl rollout undo` 回滚 |
| 5 CI | 把工程推到 GitHub，`.github/workflows/ci.yml` 自动跑 | Actions 页面观察三个 Job |

无 docker/kubectl 时能做的替代检查：

```bash
# 镜像构建上下文自检不需要 docker，但 yaml 静态校验需要 kubectl：
kubectl apply --dry-run=client -f deploy/k8s/deployment.yaml
# pom 与 examples/ex02、exercises/sol-01 同基线，可交叉对照
```

## 目录速查

| 路径 | 内容 | 验证状态 |
|------|------|---------|
| `src/main/java/com/example/myapp/` | Boot 主类 + PingController（极简探活端点） | 未在本环境验证 |
| `src/main/resources/application.yml` | 优雅停机 / 探针端点 / prometheus | 未在本环境验证 |
| `pom.xml` | 可执行 jar + 分层打包 | 未在本环境验证 |
| `Dockerfile` / `.dockerignore` | 多阶段 + 非 root + HEALTHCHECK | 未在本环境实际构建验证 |
| `docker-compose.yml` | app + mysql8 + redis7 | 未在本环境实际构建验证 |
| `deploy/sql/init.sql` | MySQL 首次初始化建表 | 未在本环境实际验证 |
| `deploy/k8s/` | namespace/config/secret/deployment/service/hpa | 未在本环境实际构建验证 |
| `.github/workflows/ci.yml` | build→test→image→deploy | 未在本环境实际构建验证 |
| `purejava/` | 纯 Java 参考实现 + 冒烟脚本 | **已验证**（OpenJDK 17.0.18 全部 PASS） |

## 为什么配一个纯 Java 参考实现

`purejava/MiniApp` 与 `app-smoke.sh` 把「Boot 可执行 jar + actuator + 配置外置 + 优雅停机」的**语义**用 JDK 自带能力逐条做出来——无 docker/mvn 的机器也能亲手验证这条部署主链；等到真实环境里跑路径 B 时，`/actuator/health` 返回什么、SIGTERM 之后日志该出现什么、配置覆盖优先级怎么走，你在冒烟里已经见过一遍。Boot 工程与纯 Java 版**端点到端点一一对应**（`/actuator/health`、`/actuator/health/liveness|readiness`、`/ping`），切换只是换实现不改验证心智。
