# examples/ex02 —— Spring Boot 打包配置 + jar 结构检查器

> 对应主文档 [3.2 Spring Boot 打包](../../19-devops-deploy.md)。本目录给「打包这一步」的完整文件：可执行 jar / 分层 jar 的 Maven 配置（`pom.xml`）、部署相关 `application.yml`，以及一个**无需 Maven 也能用的 jar 结构检查工具**（`JarLayersInspector.java`，用来亲眼验证 fat jar 与 layers.idx）。

## 文件清单

| 文件 | 作用 | 验证状态 |
|------|------|---------|
| `pom.xml` | Spring Boot 3.3.0 打包配置（repackage + 分层开关 `<layers>`），产物 `target/myapp.jar` | 未在本环境验证（无 mvn，无法离线拉 Boot 依赖） |
| `src/main/resources/application.yml` | 部署相关配置：优雅停机、探针端点、prometheus 暴露、指标 tag | 未在本环境验证（需真 Boot 应用运行） |
| `JarLayersInspector.java` | 纯 Java 17 工具：检查任意 jar 是否为 Boot 可执行 jar、统计 BOOT-INF 内容、解析 `BOOT-INF/layers.idx` | 已验证（OpenJDK 17.0.18 本机实测） |

## 验证命令

**有 Maven 的环境**（打包 + 结构检查）：

```bash
# 1. 打包（产出 target/myapp.jar 与 .jar.original）
mvn -B clean package
# 2. 直接运行（验证可执行 jar）
java -jar target/myapp.jar
# 3. 结构检查
java JarLayersInspector target/myapp.jar
```

**本机（macOS，无 mvn）—— 用纯 Java 实测检查器**（本仓库已验证的路径）：

```bash
# 1. 编译检查器
javac JarLayersInspector.java
# 2. 手工构造一个「带 BOOT-INF/layers.idx 的演示 Boot jar」/tmp/jinsp-stage 见下
# 3. 跑检查器看分层输出
java JarLayersInspector /tmp/demo-boot.jar
```

手工构造演示 jar 的命令（模拟 `mvn package` 的分层产物，验证 `layers.idx` 解析）：

```bash
# 1. 搭 staged 目录（结构模拟真实 fat jar：含 loader class 占位 → 检查器能识别「可执行」）
rm -rf /tmp/jinsp-stage && mkdir -p /tmp/jinsp-stage/BOOT-INF/classes /tmp/jinsp-stage/BOOT-INF/lib \
  /tmp/jinsp-stage/org/springframework/boot/loader
touch /tmp/jinsp-stage/BOOT-INF/classes/app.properties
touch /tmp/jinsp-stage/BOOT-INF/lib/dep-a.jar /tmp/jinsp-stage/BOOT-INF/lib/dep-b.jar
touch /tmp/jinsp-stage/org/springframework/boot/loader/JarLauncher.class
printf '%s\n' \
  '- "dependencies":' \
  '  - "BOOT-INF/lib/dep-a.jar"' \
  '  - "BOOT-INF/lib/dep-b.jar"' \
  '- "spring-boot-loader":' \
  '  - "org/"' \
  '- "application":' \
  '  - "BOOT-INF/classes/"' \
  '  - "BOOT-INF/layers.idx"' \
  > /tmp/jinsp-stage/BOOT-INF/layers.idx
# 2. 打 jar（--main-class 模拟 Boot JarLauncher 写进 MANIFEST）
jar --create --file /tmp/demo-boot.jar --main-class org.springframework.boot.loader.JarLauncher \
    -C /tmp/jinsp-stage .
# 3. 检查
java JarLayersInspector /tmp/demo-boot.jar
```

预期输出含：`是否 Spring Boot 可执行 jar : 是 (含 JarLauncher)`、依赖 2 / classes 1、三层解析（dependencies / spring-boot-loader / application 各条目数）。清理：`rm -f *.class /tmp/demo-boot.jar`。

## 教学点

- **普通 jar 不是可执行 jar**：没有 Boot loader 与 `Main-Class: JarLauncher`，`java -jar` 报 no main manifest attribute——这正是 `spring-boot-maven-plugin` 的 `repackage` 要做的事（主文档 3.2）。
- **分层让镜像缓存友好**：`layers.idx` 把「依赖 / loader / 应用」分开，Dockerfile 先 COPY 依赖层、后 COPY 应用层，改代码时只重建最后一层（主文档 3.3 的 Dockerfile 就这么写）。
- **配置外置**：`application.yml` 里的优雅停机与探针配置不随环境变；数据源地址这类环境差异走 profile / ConfigMap（主文档 3.2 末尾）。

## 生产落地点

- 本目录的 `pom.xml` + `application.yml` 即 [`project/`](../../project/) 部署模板的 Maven 侧配置。
- 结构化 JSON 日志的真实形态（logstash-logback-encoder 或 Boot 原生 JSON）见主文档 3.9；纯 Java 的最小 JSON 日志演示见 `../ex01-healthcheck-logging/`。
