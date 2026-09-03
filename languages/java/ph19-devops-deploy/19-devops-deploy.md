# Java DevOps 与部署阶段

> 面向生产交付：本阶段承接 ph18 的「单节点 Redis + 手压并发」，把能跑的 Java 服务变成能上线、能观察、能回滚的部署资产——先会用 Linux/Shell 与 Spring Boot 打包把服务跑起来，再用 Docker 镜像与 Compose 把 Java + MySQL + Redis 一键编排起来，最后用 Kubernetes/Helm 与 GitHub Actions 流水线交付「构建可复现、配置可分离、健康可探活、发布可回滚」的生产形态。

## 1. 概述

本阶段是 Java 学习路线从「功能正确」到「交付可靠」的一站。roadmap 第 19 节目标：**把 Java 服务部署到生产环境**。ph18 把缓存/锁/限流/秒杀做得再漂亮，交付时仍只是 `java -jar` 起来的一个进程——一旦要上线给真实用户用，立刻要回答一串新问题：**跑在哪台机器、崩了谁拉起（Linux/systemd）？依赖的 MySQL/Redis 怎么一起装（Compose）？换一台机器怎么原样复现（镜像）？流量大了怎么加实例、版本怎么平滑更新与回滚（K8s/Helm）？出问题怎么查日志、怎么知道它快挂了（日志/监控/健康检查）？** 本阶段就是把「一个能跑的 jar」变成「一套能交付的服务」。

ph17 与 ph18 的预告在这里逐一兑现：ph18 预告的「Docker 镜像打包秒杀 demo」（本阶段 3.2/3.3 + project 部署模板）、「健康检查」（3.5/3.11）、「日志监控」（3.9/3.10，命中率/QPS/连接池水位可观测）、「灰度发布」（3.12）；ph17 预告的「日志采集 Agent 与 Kibana 告警的部署运维属 ph19」（3.9，应用侧日志检索那段属 ph17，这里补采集与部署形态）。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 部署运行基础 | Linux 进程/端口/权限、Shell 脚本、systemd 托管、环境变量与配置外置 |
| Spring Boot 打包 | 可执行 jar（fat jar）结构、分层 jar（layers.idx）、启动参数与 profile、优雅停机配置 |
| 容器化 | Dockerfile 最佳实践（多阶段构建 / 非 root / 健康检查 / 层缓存）、镜像分层与可复现构建 |
| 编排 | Docker Compose 一键起 Java + MySQL + Redis（健康依赖、网络、卷、环境变量） |
| 集群调度 | Kubernetes 核心对象（Deployment/Service/ConfigMap/Secret/HPA）、三类探针、滚动更新与回滚 |
| 模板化交付 | Helm Chart 结构、values 参数化、install/upgrade/rollback |
| 接入层 | Nginx 反向代理与负载均衡（与 ph16 网关的分工） |
| 持续交付 | CI/CD 流水线（GitHub Actions：build → test → image → deploy） |
| 可观测性 | 结构化日志与集中采集、Actuator/Micrometer + Prometheus 指标与告警 |
| 发布策略 | 健康检查与优雅停机、蓝绿 / 金丝雀 / 滚动灰度与回滚 |

这个阶段只涉及 **Java 服务从源码到生产可观测的整条部署链路（打包 → 容器化 → 编排 → 集群 → 流水线 → 可观测 → 发布策略）**，**不涉及 JVM 深水区（GC 调优、JMM/AQS 源码级机制、Netty 高性能网络）与大型工程模式（DDD/反射 SPI）** — 那是 [ph20 高级 Java 阶段](../ph20-advanced-java/20-advanced-java.md)——本阶段只按生产需要给出容器内 JVM 内存参数 `-XX:MaxRAMPercentage` 的用法，不深入 GC 选型与调优、**不涉及车联网业务整合（车辆接入/告警规则/OTA 平台如何用本阶段模板部署）** — 那是 ph21 车联网 / 智能电动车方向 Java 阶段（roadmap 第 21 节，目录待建）、**不重复 ph15 的 actuator 端点枚举与 ph16 的微服务治理框架（Sentinel/网关熔断规则）**（本阶段在 nginx 反代处只讲部署形态，治理规则仍在 ph16）、**不重讲 ph17 的 ES 检索 DSL 与 ph18 的秒杀并发语义**（本阶段只在其日志采集与镜像打包处引用结论）。中间件（Redis/MySQL/ES/Kafka）自身的集群分片与选主不在本 roadmap 的后续阶段中——本阶段只把它们作为 compose/K8s 清单里「被部署的对象」，用官方镜像的标准姿势拉起，不展开分片原理。

## 2. 来源与演变

**DevOps 的本质是「把部署与运维变成一等公民的开发活动」**——这句话值得加粗。它的源头可以追到 2007~2009 年：当时敏捷开发已经把「写代码」的周期压到周/天级，但「上线」仍是手工、低频、高风险的黑箱操作，开发与运维互相甩锅。2009 年比利时根特的 **DevOpsDays** 给这场运动命了名，同年 Flickr 的《10+ Deploys Per Day》演讲展示了「开发与运维协作 + 自动化部署」的可行形态；此后业界用 CAMS/CALMS 概括其价值观——Culture（协作文化）、Automation（自动化一切可自动的）、Lean（精益/消除浪费）、Measurement（一切用指标说话）、Sharing（共享责任与经验）。

容器化是支撑这场运动的**技术地基**，其思想比 Docker 老得多：**容器 = 操作系统级虚拟化，「一个内核、多份隔离的用户空间」**。1979 年 Unix V7 就有了 `chroot`（改根目录，最早的目录隔离）；2006 年 Google 工程师在内核引入 **cgroup**（资源限制），2008 年并入 Linux 2.6.24；同期 PID/网络等 **namespace**（视图隔离）陆续并入内核——这两个机制正是容器「隔离 + 限量」的全部底层。2008 年 **LXC** 把它们封装成易用的容器工具；2013 年 3 月 dotCloud（Solomon Hykes）把自家平台里的容器技术开源为 **Docker**，用「镜像 = 分层只读文件系统 + 统一命令 + 镜像仓库」把容器的易用性做到爆发——开发者第一次能像管理源码一样管理环境。2014 年 Google 开源 **Kubernetes**（源自内部 Borg/Omega），把「管一台机器上的容器」升级为「管一群机器上的容器」；同年 Docker 官方发布 Compose（前身是 fig）；2015 年 Deis 团队开源 **Helm**（K8s 的包管理）。此后 OCI（2015）把镜像与运行时格式标准化，containerd（2017）成为 K8s 默认运行时——生态在 2018 年完成「Docker 管镜像与单机运行、K8s 管编排」的分工定型。

Java 的部署形态同步走过四代，每一代解决上一代的一个痛点，这张表是本阶段 3.x 的「为什么这样设计」索引：

| 里程碑 | 年份 | 部署形态 | 解决的痛点 | 遗留问题 |
|------|------|---------|-----------|---------|
| WAR 时代 | 2000~ | 打包成 `.war` 丢进外部 Tomcat | 统一 servlet 容器、可热部署 | 容器与应用耦合、环境差异、「在我机器上能跑」 |
| 可执行 fat jar | 2014（Spring Boot 1.0） | `java -jar app.jar`（内嵌 Tomcat） | 应用自带容器，一个命令跑起来 | 体积大（含全部依赖）、分层不清晰、镜像层缓存差 |
| 分层 jar | 2020（Boot 2.3） | `BOOT-INF/layers.idx` 分依赖/应用层 | 镜像构建时依赖层可复用缓存、应用层才常变 | 仍需手动编排镜像层顺序 |
| 容器镜像 + K8s | 2013~2014 起 | 镜像不可变交付 → 集群声明式编排 | 环境可复现、扩容/滚动/回滚自动化 | 引入了容器网络/存储/编排的新复杂度 |

> 真实生产环境里这四代形态**仍然并存**：小工具裸 jar + systemd、中型服务 Docker + Compose、规模化服务 K8s + Helm——本阶段全部覆盖，5 章给出选型档位。

本文示例以 **OpenJDK 17 + Maven 3.9 + Spring Boot 3.3.0 + Docker 24 + Docker Compose v2 + Kubernetes 1.28+ + Helm 3 + GitHub Actions（ubuntu-latest runner）** 为基线（选择理由：与 ph14~ph18 完全同基线，Boot 3.3 是 roadmap 示例代码的共同版本；K8s/Helm 只用到多年未变的稳定 API，如 `apps/v1`、`autoscaling/v2`）。**本机（macOS）验证纪律**：无 docker、无 mvn、无 helm/kubectl——① 纯 Java 可实测的部分（ex01 健康检查/结构化日志/优雅停机、ex02 的 jar 结构检查工具、project 的纯 Java 参考实现与冒烟脚本）已在 **OpenJDK 17.0.18** 本机实测并标注「已验证」；② 依赖 docker/mvn 的部分（镜像构建、compose 起服务、`mvn package`）标注「未在本环境验证」，各文件给出可复现命令；③ Dockerfile/Compose/K8s/Helm/GitHub Actions/Shell 脚本属于「写出来即交付物」，标注「未在本环境实际构建验证」并给出验证命令（其中 Shell 脚本额外用本机 `bash -n` 做过语法校验）。roadmap 第 19 节示例里的 `eclipse-temurin:21-jre` 是示意（21 为当时 LTS），本文档统一用 **17-jre** 保持与学习基线一致——Java 17 与 21 的容器运行姿势完全相同，只差基础镜像 tag。

## 3. 语法与参数

### 3.1 Linux/Shell 部署基础：服务不是跑起来就完了

Java 服务最终要跑在 Linux 上，第一课是「进程的一生」：一个 jar 用 `java -jar` 启动后，它变成一个前台进程——**关掉终端它就死**（SIGHUP）。所以部署的最原始问题是「怎么让它脱离终端活着、崩了自动拉起、开机自动启动」。手工时代的姿势是 `nohup`：

```bash
# Linux 部署的第一课：脱离终端 + 日志落盘 + 记录 PID（未在本环境执行，命令面向 Linux）
nohup java -Xmx512m -jar /opt/myapp/app.jar --spring.profiles.active=prod \
  > /var/log/myapp/app.log 2>&1 &
echo $! > /var/log/myapp/app.pid      # $! = 刚启动的后台进程 PID，用于后续 kill/查询
```

但 `nohup` 只管「脱离终端」，**不负责崩溃重启、不负责开机自启**。现代 Linux 用 **systemd** 管服务，声明式描述「这个服务怎么起、崩了怎么办、依赖什么」（examples/ex07-script-deploy 给了完整 unit）：

```ini
# /etc/systemd/system/myapp.service —— 托管 Java 服务（systemd 会把输出收进 journald）
[Unit]
Description=MyApp Spring Boot Service
After=network.target           # 声明依赖：网络就绪后才启动本服务

[Service]
User=myapp                     # 用独立低权限用户跑，别用 root
Environment=SPRING_PROFILES_ACTIVE=prod
ExecStart=/usr/bin/java -Xmx512m -jar /opt/myapp/app.jar
Restart=on-failure             # 非正常退出自动拉起（0 退出码 = 正常停机，不重启）
RestartSec=3
TimeoutStopSec=30              # 配合 3.11 优雅停机：先 SIGTERM 等 30s 再 SIGKILL

[Install]
WantedBy=multi-user.target     # 开机自启
```

Shell 脚本是手工运维时代的胶水（自动发布、备份、巡检都靠它），本阶段只要求会读会写基础脚本，全部用**现代 bash 安全默认**——`set -euo pipefail`（出错即停 / 未定义变量报错 / 管道失败要暴露），这是无数生产事故换来的三行默认（examples/ex07 的 deploy.sh 即其模板）：

```bash
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="/opt/myapp"
is_up() { curl -fsS http://127.0.0.1:8080/actuator/health >/dev/null; }   # 函数封装探活
```

部署排查的基本功是几组命令：`systemctl status myapp` 看服务状态、`journalctl -u myapp -f` 看日志（代替翻文件）、`lsof -i :8080` 查端口占用、`ss -lntp` 看监听、`free -h` / `top` / `df -h` 看资源、`kill -TERM <pid>` 发优雅停机信号。**为什么这些是必会**：容器化之后它们依然有效（进容器 `docker exec` 后是同一套 Linux），且排障顺序永远是「先看状态 → 再看日志 → 再查资源」，乱序会浪费时间。

### 3.2 Spring Boot 打包：从 `mvn package` 到可执行 jar

Spring Boot 把「部署单元」从外部容器里的 WAR 变成自带容器的 **可执行 jar（fat jar）**——`mvn package` 后 `target/` 里那个 jar 直接 `java -jar` 就能跑，因为它内部塞了三样东西：

```text
myapp.jar（可执行 fat jar 的内部结构，可用 unzip -l 查看）
├── BOOT-INF/classes/          ← 你自己的 class 与 resources（application.yml 在这里）
├── BOOT-INF/lib/              ← 全部第三方依赖 jar（所以叫 fat，几十 MB 是常态）
├── org/springframework/boot/loader/   ← Boot 自带的 JarLauncher（负责从嵌套 jar 加载类）
└── META-INF/MANIFEST.MF
    Main-Class: org.springframework.boot.loader.JarLauncher   ← java -jar 的入口
    Start-Class: com.example.myapp.MyAppApplication            ← 真正的主类（含 main）
```

**为什么不用普通 `mvn package` 打出的 jar**：没有 `spring-boot-maven-plugin` 的 `repackage`，打出的只是普通 jar——依赖在 `BOOT-INF/lib` 里但 JVM 的 classpath 机制不认识嵌套 jar，`java -jar` 会报「no main manifest attribute」。Boot 插件的 `repackage`（默认绑定 `package` 阶段）把普通 jar 改造成上面这种自带加载器的形态，同时保留一份 `.jar.original` 备份原始 jar。**分层 jar（layers.idx）** 是 2.3 起的优化：默认把内容按「依赖 / spring-boot-loader / snapshot 依赖 / 应用自身」分成四层，让 Docker 构建时「依赖层几乎不变可命中缓存、只有应用层常变」——这是 3.3 镜像加速的关键前置：

```xml
<!-- pom.xml 关键片段（完整文件见 examples/ex02-spring-boot-jar-packaging/pom.xml，未在本环境验证：无 mvn）
     spring-boot-starter-parent 已托管 Boot 插件版本，这里只开分层开关 -->
<build>
  <plugins>
    <plugin>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-maven-plugin</artifactId>
      <configuration>
        <layers>
          <enabled>true</enabled>      <!-- 生成 BOOT-INF/layers.idx，配合镜像按层 COPY -->
        </layers>
      </configuration>
    </plugin>
  </plugins>
</build>
```

打包只解决「产物」，**运行时配置外置**解决「配置与代码分离」（roadmap 必会概念）：同一个 jar 不应该因环境（dev/prod）而变，变的是外部的配置来源。Boot 的配置优先级从高到低大致是：命令行参数 > 环境变量 > profile 专属文件 > `application.yml`——部署时最常用两招：`java -jar app.jar --spring.profiles.active=prod`（命令行）或 `SPRING_PROFILES_ACTIVE=prod` 环境变量，配合 `application-prod.yml` 把「环境相关的值」（数据源地址、密码、日志级别）外置。这个「**jar 不变、配置随环境注入**」正是 3.4 compose、3.5 ConfigMap、3.6 values.yaml 全部在做的事的根源——镜像与配置必须分离，否则每换一个环境就重打一次镜像，可复现与可回滚都无从谈起。

### 3.3 Dockerfile 最佳实践：把「能跑」变成「可复现」

Docker 解决的是 ph14 之前就有的老毛病——「在我机器上能跑」。**镜像 = 文件系统的可复现快照**：基础 JDK、应用 jar、启动命令都被钉进一个不可变产物，`docker run` 在任何装有 Docker 的机器上跑出同一行为。Dockerfile 是构建这个镜像的「配方」，五条最佳实践对应五个为什么（完整文件见 examples/ex03）：

```dockerfile
# examples/ex03-dockerfile-compose/Dockerfile —— 完整可运行版见 examples/（未在本环境实际构建验证：无 docker）
# 1) 多阶段构建：第一个阶段只负责「编译出 jar」，产物不留进运行镜像
FROM maven:3.9-eclipse-temurin-17 AS builder
WORKDIR /build
COPY pom.xml .
RUN mvn -B dependency:go-offline          # 先把依赖拉全（利用镜像层缓存，pom.xml 不变这层不重跑）
COPY src ./src
RUN mvn -B -DskipTests package            # 产出 target/app.jar

# 2) 运行镜像只放「运行需要的最小集」：JRE 而非 JDK、无 maven、无源码
FROM eclipse-temurin:17-jre
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*        # curl 供 HEALTHCHECK/探活用（K8s 用探针则可不装，见 3.11）
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
# 3) 分层 jar 按层 COPY：依赖层在前 → 只改代码时依赖层直接命中构建缓存
COPY --from=builder /build/target/app.jar app.jar
# 4) 非 root 运行：容器内进程被攻破时权限被限制在 appuser（不是镜像逃逸到宿主 root 的钥匙）
USER appuser
EXPOSE 8080
# 5) HEALTHCHECK：给 docker/compose 层一个「容器内自检」的出口（K8s 环境不依赖它，用探针）
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8080/actuator/health || exit 1
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75.0", "-jar", "/app/app.jar"]
```

每条实践背后的理由，是这份 Dockerfile 的「为什么」：

| 最佳实践 | 解决什么 | 不做的后果 |
|---------|---------|-----------|
| 多阶段构建 | 运行镜像里不残留编译工具与源码 | 镜像多几百 MB、攻击面大（镜像里有 mvn = 有代码与工具） |
| 分层 jar + 依赖层先 COPY | 代码改动不重下依赖、不重跑 mvn | 每次构建全量重来，CI 慢且构建缓存失效 |
| 非 root（USER appuser） | 容器进程逃逸后的横向权限最小化 | 攻击者拿到容器内 root 可直接操作宿主权限边界内的资源 |
| HEALTHCHECK | 容器运行时（docker/compose）可感知服务死活 | compose 的 `depends_on: service_healthy` 无法工作 |
| 显式 ENTRYPOINT + JVM 参数 | 启动命令可复现、容器限内存时 JVM 能感知（4.4） | 启动参数散落在 run 命令里，换人启动行为就漂移 |

> 本阶段不展开镜像仓库（Registry）推送的私有化细节，只记住「镜像要打 **不可变 tag**（Git SHA 或版本号），**绝不覆盖 `latest` 当发布物**」——latest 会漂移，漂移的镜像无法回滚到「上一次那个确切的东西」。这是「发布必须可回滚」的地基。

### 3.4 Docker Compose 编排：Java + MySQL + Redis 一键起来

单个容器跑一个应用解决不了「应用依赖中间件」的问题——本地开发、单机演示时，最痛苦的是「先装 MySQL、再装 Redis、再配网络连上去」。**Compose 用一份 YAML 声明式定义一组服务**（每个服务 = 一个镜像 + 参数），`docker compose up -d` 一条命令按依赖顺序拉起整组，`down` 一键清理。它的心智模型是「**单机多容器项目的工程文件**」（`docker-compose.yml` 之于 docker 像 `pom.xml` 之于 mvn）：

```yaml
# examples/ex03-dockerfile-compose/docker-compose.yml —— Java(构建自本地 Dockerfile) + MySQL 8 + Redis 7（未在本环境实际构建验证）
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root123
      MYSQL_DATABASE: myapp
      MYSQL_USER: app
      MYSQL_PASSWORD: app123
    volumes:
      - mysql-data:/var/lib/mysql          # 数据落命名卷：容器删了数据还在
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro   # 首次启动自动建表（官方镜像约定路径）
    healthcheck:                            # 服务级健康检查（下文的就绪依赖要用它）
      test: ["CMD", "mysqladmin", "ping", "-h", "127.0.0.1", "-papp123"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--requirepass", "redis123"]
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "redis123", "ping"]

  app:                                     # Java 应用：本地 Dockerfile 构建（build 上下文 = 当前目录）
    build: .
    image: myapp:dev
    depends_on:                            # v2 的「健康依赖」：等 mysql/redis 探活成功才启动 app
      mysql:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      SPRING_PROFILES_ACTIVE: compose
      DB_HOST: mysql                       # 服务名即 DNS：应用里连 "mysql:3306" 而非 localhost
      REDIS_HOST: redis
    ports:
      - "8080:8080"
    mem_limit: 512m                        # 与 3.3 ENTRYPOINT 的 MaxRAMPercentage 配套（4.4 讲为什么）

volumes:
  mysql-data:
```

**为什么 Compose 解决「Java 服务上生产的第一站」**：它把「依赖服务 + 顺序 + 网络 + 数据卷」都声明化，`up -d` 拉起的拓扑与生产 K8s 里的多 Pod 拓扑同构——在 compose 里理解了「应用通过服务名而不是 IP 找依赖、健康检查决定启动顺序、数据进卷不进容器层」，迁移到 K8s 只是换一套对象名（3.5）。**三个高频坑**：① `depends_on` 不带 `condition: service_healthy` 时只保证「容器起了」不保证「服务可用」，MySQL 还在初始化时应用就连库失败（所以必须配健康检查 + 健康依赖）；② 应用里连数据库要写服务名 `mysql` 而不是 `localhost`——每个容器有自己的网络命名空间（4.1），`localhost` 是容器自己；③ 容器内的数据默认写在容器可写层，容器一删数据就没了——**一切要留的数据必须进 volume**。

### 3.5 Kubernetes：Deployment 声明「要什么」，控制面负责「做到」

Compose 管一台机器，**Kubernetes 管一群机器**。它的核心思想一句话：**你声明期望状态（desired state），控制面不断把现实收敛到期望状态**——这就是声明式编排。要跑 3 个副本、探针长什么样、镜像哪个版本，都写进清单（manifest）；节点挂了控制面会自动补副本，不需要人 SSH 上去重启。

本阶段要会五个对象（roadmap 的 Kubernetes 部署练习 + 必会概念「服务需要健康检查」全在这）：

| 对象 | 一句话职责 | 关键字段 |
|------|-----------|---------|
| **Deployment** | 管一组无状态副本（滚动更新/回滚/副本数） | `replicas`、`strategy`、`template.spec` |
| **Service** | 给一组 Pod 一个稳定的访问入口（DNS + 负载均衡） | `selector`（按 label 挑 Pod）、`type` |
| **ConfigMap / Secret** | 配置与敏感数据外置，镜像不随环境变 | `data` / `stringData`，注入方式：环境变量或文件 |
| **探针（Probe）** | kubelet 定期问「这个容器还活着吗/能接流量吗」 | `startupProbe` / `livenessProbe` / `readinessProbe` |
| **HPA** | 按 CPU/自定义指标自动扩缩副本 | `minReplicas` / `maxReplicas` / `metrics` |

Deployment + Service + 探针的最小可跑形态（完整文件见 examples/ex04-k8s-manifests）：

```yaml
# examples/ex04-k8s-manifests/deployment.yaml —— 核心片段（未在本环境实际构建验证：无 kubectl/集群）
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0        # 滚动期间不允许少于期望副本数 → 先起新的再停旧的，零停机前提
      maxSurge: 1              # 最多额外多起 1 个新副本
  selector:
    matchLabels: { app: myapp }
  template:
    metadata:
      labels: { app: myapp }
    spec:
      containers:
        - name: myapp
          image: myregistry/myapp:1.4.2      # 不可变 tag：回滚目标
          ports: [{ containerPort: 8080 }]
          envFrom:                           # 配置外置：ConfigMap 注入环境变量
            - configMapRef: { name: myapp-config }
          resources:
            requests: { cpu: 250m, memory: 512Mi }   # 调度依据：保证给这么多
            limits:   { cpu: "1",   memory: 1Gi }    # 上限：配合 MaxRAMPercentage（4.4）
          startupProbe:      # 慢启动服务的「请等我」：失败阈值 30 × 2s = 最多 60s 让 JVM 起来
            httpGet: { path: /actuator/health/liveness, port: 8080 }
            failureThreshold: 30
            periodSeconds: 2
          readinessProbe:    # 就绪探针：false 时从 Service 摘除，不接新流量（滚动更新的正确性靠它）
            httpGet: { path: /actuator/health/readiness, port: 8080 }
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:     # 存活探针：连续失败 kubelet 杀容器重启（死锁/内存泄漏的兜底）
            httpGet: { path: /actuator/health/liveness, port: 8080 }
            initialDelaySeconds: 20
            periodSeconds: 10
```

**三类探针的分工是生产事故的高发考点**：`livenessProbe` 失败 = 容器死锁/彻底不可救，杀之重启；`readinessProbe` 失败 = 还没就绪或过载，摘流量但不杀（**摘流量 ≠ 杀进程**，这俩语义绝不能混）；`startupProbe` 专门给启动慢的服务（JVM 冷启动、连依赖）一个「先别杀我」的宽限期。**常见错误**：把 DB 连通性放进 liveness——DB 抖动会让所有实例连环被杀重启（雪崩式重启风暴），正确做法是 DB 状态只影响 readiness（不让新流量进）而不影响 liveness（进程本身没死）。探针的语义正确性直接决定 3.12 滚动更新与回滚能不能零事故。

`Service` 是让上面这些 Pod 可被访问的稳定入口：`selector` 用 label 挑中带 `app: myapp` 的 Pod，`type: ClusterIP` 给集群内虚拟 IP + DNS，外部流量经 Ingress/Nginx（3.7）进入。**为什么 Pod 不能直接作为访问单位**：Pod 的 IP 是临时的（重建即换），Service 提供「不变的 DNS + 自动跟随后端列表」，消费方永远只认 Service 名。

### 3.6 Helm：K8s 清单的「模板化 + 版本化」

直接 `kubectl apply -f` 一份份 YAML 有三个痛点：**环境差异**（dev 副本 1 个、prod 要 5 个——清单不能复制十份）、**参数散落**（镜像版本、副本数、资源上限埋在几十行 YAML 里，改一处要翻半天）、**无法回滚**（`apply` 没有「这次改动是什么」的概念）。**Helm = K8s 的包管理器**：一个 Chart 是一份带 `{{ .Values.xxx }}` 占位符的清单模板 + 一份 `values.yaml`（默认参数）。部署时 `helm install myapp ./chart --set image.tag=1.4.2`，Helm 用参数渲染出具体清单再交给 K8s，并把每次部署记为 **release**——于是天然获得 `helm upgrade` 与 `helm rollback myapp 1`（一键回退到上一个 release）。

```yaml
# examples/ex05-helm-chart/values.yaml —— 全部可变点集中在这一个文件（核心片段，完整 Chart 见 examples/ex05）
replicaCount: 2
image:
  repository: myregistry/myapp
  tag: "1.4.2"              # 部署时 --set image.tag=... 覆盖
  pullPolicy: IfNotPresent
probes:
  readinessPath: /actuator/health/readiness
resources:
  requests: { cpu: 250m, memory: 512Mi }
  limits:   { cpu: "1", memory: 1Gi }
```

```yaml
# examples/ex05-helm-chart/templates/deployment.yaml —— 模板片段：values 注入 + 参数化
spec:
  replicas: {{ .Values.replicaCount }}
  template:
    spec:
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          readinessProbe:
            httpGet: { path: {{ .Values.probes.readinessPath }}, port: 8080 }
```

**为什么是 Helm 而不是脚本 `sed` 替换 YAML**：模板是有结构的安全渲染（不会破坏 YAML 缩进），release 自带历史版本（回滚有明确目标），`helm lint`/`helm template` 可在不上集群的情况下校验渲染结果——这些是脚本替换给不了的工程保证。Helm 的定位就是「**把『怎么部署这个 Java 服务』固化成一份可评审、可版本化、可回滚的资产**」，与 3.8 流水线里的 deploy 步骤直接衔接。

### 3.7 Nginx 反向代理：流量进集群前的最后一站

K8s 只解决「集群内」的流量，外部请求怎么进到 Service 是另一层。**Nginx 在本阶段承担反向代理与负载均衡**：客户端只认识 `https://api.example.com`，Nginx 按 `location` 把请求转发到后端服务（可以是 Docker 容器、Compose 服务或 K8s 的 Ingress controller 后端）：

```nginx
# 本文档演示片段（未落 examples 文件，仅展示 Nginx 反代配置形态；未在本环境实际构建验证）
upstream myapp_backend {
    server myapp:8080 max_fails=3 fail_timeout=10s;   # compose 网络里服务名即 DNS
}
server {
    listen 80;
    location /api/ {
        proxy_pass http://myapp_backend;               # 反代：客户端无感知，Nginx 代它访问后端
        proxy_set_header Host $host;                   # 透传原始 Host/X-Forwarded-* 给后端
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**为什么生产要有这一层**：卸载 TLS（证书集中管理，Java 侧不用管）、统一入口做静态资源服务与访问日志、给后端做负载均衡与故障摘除。它与 ph16 的微服务网关（Gateway/Sentinel）**不是替代关系而是分层关系**：Nginx 管「南北向」的外部流量进集群的入口（卸载 TLS、粗粒度路由），网关管「东西向」或入口后的服务治理（鉴权、限流、熔断规则，ph16）。判断一句话：**Nginx 是部署层物件（管连接），网关是治理层物件（管业务规则）**。

### 3.8 CI/CD：GitHub Actions 把「人肉上线」变成「提交即发布」

手工上线是 DevOps 要消灭的头号敌人：SSH 上去、拉代码、重启、拜一拜——不可复现、不可审计、出错只能靠人回忆。**CI/CD 把「构建 → 测试 → 打包镜像 → 部署」写成代码放进仓库**，每次 `git push` 自动执行（examples/ex06-github-actions 给了完整文件）：

```yaml
# examples/ex06-github-actions/.github/workflows/ci.yml —— 核心流程（未在本环境实际构建验证：需 GitHub 托管 runner）
name: build-test-deploy
on:
  push:
    branches: [main]
  pull_request:

jobs:
  build-test:                                  # Job 1：质量门禁
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4              # 取代码
      - uses: actions/setup-java@v4            # 装 JDK（缓存 maven 依赖）
        with: { distribution: temurin, java-version: '17', cache: maven }
      - run: mvn -B -ntp test                  # 测试不过 = 整条流水线停在这里
      - run: mvn -B -ntp -DskipTests package   # 产出可执行 jar（3.2）
      - uses: actions/upload-artifact@v4
        with: { name: app-jar, path: target/app.jar }

  build-image:                                 # Job 2：推镜像（等 Job 1 绿）
    needs: build-test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3           # 登录镜像仓库（本示例用 GHCR，token 自动注入）
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6      # buildx 多架构构建 + 推送不可变 tag（Git SHA）
        with:
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ github.sha }}

  deploy:                                      # Job 3：部署到 K8s（生产分支才跑，靠 environment 门禁）
    needs: build-image
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: prod                          # environment 可挂人工审批（生产发布前点一下）
    steps:
      - uses: actions/checkout@v4
      - run: helm upgrade --install myapp ./deploy/chart \
              --namespace prod --set image.tag=${{ github.sha }}
        env:                                   # KUBECONFIG 内容放 Actions Secret，流水线不落盘
          KUBECONFIG: ${{ secrets.KUBECONFIG }}
```

**为什么流水线要拆三个 Job 而不是一个脚本跑到底**：每个 Job 是一道门禁——测试挂了不碰镜像、镜像没推成功不碰集群、deploy 只在 main 分支 + 手动审批的 environment 上执行。**每道门只让「前一步验证过的产物」往后流**，这就是 CI/CD 与「一个巨大的 bash 脚本」的本质区别：可观测（哪一步挂了看 Actions 日志）、可重放（同样提交永远走同样流程）、产物不可变（deploy 的是 Git SHA 打出的镜像，不是「当时工作区里有什么」）。Jenkins 与 GitHub Actions 是同一心智的两种宿主：**流水线即代码**，jenkins 用 `Jenkinsfile`（自托管、插件生态）、Actions 用 workflow YAML（托管 runner、与代码仓库同托管）；中小企业没有自建 CI 设施时 Actions 是零运维的默认选择。

### 3.9 日志采集：从「ssh 上去 tail」到「结构化日志集中查」

单机时代日志是文件，`tail -f app.log` 就能看。**服务一多（ph16 微服务）+ 容器化后，日志的形态必须改**，两个根本变化：

1. **日志要进 stdout 而不是写文件**。容器/Pod 随时被重建，写进容器文件系统的日志随容器一起消失；Docker/K8s 约定「应用把日志打到标准输出/错误」，运行时统一收集——这是 3.3 的镜像里**不该有 log 目录**的原因。
2. **日志要结构化而不是拼字符串**。人肉 `tail` 看的是行文本，集中检索（ph17 的 ES）与告警要的是字段——`time`、`level`、`logger`、`traceId`、`msg`、业务键值。所以生产姿势是 **JSON 行日志**（每行一个 JSON 对象），Java 侧靠 logback 的 `logstash-logback-encoder` 或 Boot 的 JSON 日志支持（examples/ex01 用纯 Java 手写了一个最小 JSON logger，演示「结构化 = 什么」）：

```text
# 结构化日志行示例（一行一个 JSON，采集端无需解析文本就能按字段检索/告警）
{"ts":"2026-09-03T10:11:22.345+08:00","level":"ERROR","logger":"com.example.OrderService",
 "msg":"failed_deduct_stock","traceId":"8f3a1c…","orderId":"o-1001","skuId":"sku-9","stock":0}
```

集中采集的部署拓扑（兑现 ph17 预告：「采集 Agent 与 Kibana 告警的部署运维属 ph19」）：

```text
应用(JSON stdout) ──▶ 节点级采集 Agent(Filebeat/Fluent Bit/Promtail) ──▶ 检索/存储(ES-Loki)
                              ▲
        K8s 里 Agent 以 DaemonSet 部署：每个节点一个，自动发现该节点全部 Pod 的日志
        （不用往每个应用镜像里塞采集器，应用只负责「把结构化日志打 stdout」）
```

**为什么采集 Agent 要在节点上而不是应用里**：应用镜像保持「只含应用」，采集是平台的横切职责——换采集方案（Filebeat → Promtail）不用改一行应用代码、不用重打镜像。这是贯穿全阶段的**关注点分离**：应用只负责「输出结构化日志 + 读配置 + 暴露健康与指标」，平台负责「收集、存储、告警」。

### 3.10 监控告警：Actuator 暴露指标，Prometheus 定时来抓

日志回答「发生了什么」，指标回答「正在恶化吗」。**Java 侧的指标栈是 Actuator + Micrometer + Prometheus**：Micrometer 是**指标门面**（像 SLF4J 之于日志），应用代码与框架把各种计数注册成指标；Actuator 把 JVM/HTTP/HikariCP/Caffeine/Redis 的 Micrometer 指标在 HTTP 端点暴露；Prometheus 周期性来「抓」（scrape）并存储；告警规则命中时 Alertmanager 发通知。配置只需两步：

```yaml
# application.yml 相关片段（完整见 examples/ex02/application.yml，未在本环境验证：需引入 micrometer-registry-prometheus 依赖）
management:
  endpoints:
    web:
      exposure:
        include: health,info,prometheus     # 把 /actuator/prometheus 端点开出来给 Prometheus 抓
  endpoint:
    health:
      probes:
        enabled: true                        # 开放 /actuator/health/liveness|readiness（3.5 探针路径）
```

```yaml
# prometheus.yml —— 抓取配置：告诉 Prometheus 每隔几秒去哪个地址抓指标（部署形态见 examples/ex03）
scrape_configs:
  - job_name: myapp
    metrics_path: /actuator/prometheus
    static_configs:
      - targets: ["myapp:8080"]              # compose 网络内直接服务名抓取
```

**为什么这套设计把「可观测」变简单了**：应用完全不感知 Prometheus 的存在——它只是「把指标暴露在一个端点」，谁抓、多久抓一次是平台配置。ph18 预告的「命中率、QPS、连接池水位都要可观测」在这里自动兑现：Micrometer 为连接池暴露 `hikaricp_connections_*`、为缓存暴露 `cache_gets_total`/`cache_evictions`（Caffeine 命中率的原料）、为 Redis 暴露命令计数、Web 层暴露 HTTP QPS 与延迟直方图——**不用写一行采集代码**，指标就在 `/actuator/prometheus` 里。告警闭环（Alertmanager）的常见规则：P99 延迟超阈值、错误率突增、连接池耗尽、堆使用率持续高位——规则文件同样「写出来即交付物」，验证方式是本地起 Prometheus 看 `up == 1` 且能拉到 `jvm_memory_used_bytes`。

### 3.11 健康检查与优雅停机：发布正确性的两个基石

健康检查 3.5 已给配置，这一节讲**为什么健康检查必须配合优雅停机**，否则滚动更新时旧实例被杀、新实例未就绪，中间会出现请求打到「正在被杀的实例」上。一次零事故滚动更新的完整时序：

```text
新版本 Deployment 提交
   ▼
① 新 Pod 启动 → startupProbe 放行（JVM 起来、连上依赖）
   ▼
② readinessProbe 转 UP → Service 开始把流量分给新 Pod
   ▼
③ 旧 Pod 收到 SIGTERM → Spring 触发优雅停机（server.shutdown=graceful）：
   先停止接收新连接 → 等 in-flight 请求自然结束（最多等 spring.lifecycle.timeout-per-shutdown-phase）
   ▼
④ 旧 Pod 处理完存量请求后退出 → 若超时未退完，kubelet 在 terminationGracePeriodSeconds 后 SIGKILL
```

Java 侧要做的两件事配置起来各一行：

```yaml
# application.yml —— 优雅停机（未在本环境验证：需真 Boot 应用）
server:
  shutdown: graceful                       # Boot 收到 SIGTERM 后优雅关停，而非立刻断连接
spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s        # 每个关停阶段最多等 30s，超时强制结束
```

```yaml
# k8s 清单片段 —— preStop hook：先给 LB 摘除留几秒缓冲，再让容器退（完整见 examples/ex04）
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 5"]   # 让 Service 把本 Pod 从端点列表摘除后再 SIGTERM
terminationGracePeriodSeconds: 40             # 必须 > preStop sleep + 优雅停机超时
```

**三个为什么**：① **优雅停机为什么先拒新连接再等存量**——直接杀进程会丢正在处理的请求（用户看到 500/连接重置），先拒新后等旧保证「存量请求有始有终」；② **readiness 为什么在 SIGTERM 前就要转 FAIL**——Boot 收到 SIGTERM 进入关停时会把 readiness 自动置 FAIL（K8s 摘流量），但 preStop sleep 给了摘除传播的时间，防止「K8s 还没摘完就杀」；③ **超时为什么必要**——没有超时，一个挂死的请求能让 Pod 永远退不掉，`terminationGracePeriodSeconds` 是最后的强制兜底。这套时序 3.5 的三类探针 + 这里的优雅停机 + 3.12 的滚动策略，**三者合起来才叫「零停机发布」**——缺任何一环都有流量黑洞窗口。

### 3.12 灰度发布与回滚：发布必须可回滚

roadmap 必会概念「发布必须可回滚」——不是「最好有回滚」，而是**发布流程的设计默认包含回滚路径**。三种策略的取舍：

| 策略 | 机制 | 优点 | 缺点 | 适用 |
|------|------|------|------|------|
| 滚动更新 | 逐批替换（K8s 默认，3.5 的 maxSurge/maxUnavailable） | 不停机、无额外资源 | 新旧并存窗口长、问题要等监控发现 | 默认选择 |
| 蓝绿 | 新版本整套环境（绿）就绪后，流量一次性从旧（蓝）切到新 | 切换干脆、回滚 = 再切回去 | 双倍资源、环境间差异要管 | 资源充裕、切换要求快的核心服务 |
| 金丝雀 | 先放 1%~10% 流量给新版本，指标稳定后逐步放量 | 真实流量小范围验证、风险最小 | 需要流量权重控制（nginx/Istio/Argo Rollouts） | 大版本、高风险变更 |

K8s 原生给的是滚动更新 + `kubectl rollout undo`，金丝雀的权重控制要用 Ingress/Nginx 或 Argo Rollouts（概念性提及，接入不展开）：

```bash
# 滚动更新的日常三连（未在本环境执行：无集群）
kubectl set image deployment/myapp myapp=myregistry/myapp:1.5.0     # 触发滚动（等价于 apply 新清单）
kubectl rollout status deployment/myapp                              # 等滚动完成（内部在等 readiness）
kubectl rollout undo deployment/myapp                                # 出问题：一键回滚到上一个 revision
```

**为什么必须「不可变 tag + 自动回滚路径」**：回滚的本质是「把运行态退回某个已知良好的历史版本」——镜像 tag 不可变（3.3）保证「历史版本还在且未变」，Deployment 的 `revisionHistoryLimit`（默认保留 10 个 revision）保证「能退到上上个版本而不只是上一个」。回滚的**触发信号是监控而不是人肉报告**：这就是 3.10 的告警 + 3.11 的探针存在的意义——金丝雀放量到 100% 前，指标窗口内没有 ERROR 突增才继续；一旦告警，`rollout undo` 或 `helm rollback` 在一分钟内完成。**发布策略的完整闭环 = 不可变镜像（3.3）+ 配置外置（3.2/3.5）+ 探针与优雅停机（3.5/3.11）+ 监控告警（3.10）+ 回滚路径（本节）**，这正是 7 章验收清单的组织方式。

## 4. 底层原理

### 4.1 容器运行时：namespace 隔离视图，cgroup 限量资源，overlayfs 省空间

容器不是虚拟机——**容器里的进程就是宿主机上的进程**，只是被三个内核机制包装过（这正是 Docker 比 VM 轻量、秒级启动的根源）：

```text
一个容器进程的三个包装层
┌─────────────────────────────────────────────────────┐
│ namespace：我看不到系统全貌 —— 隔离「视图」            │
│   PID namespace  → 容器里自己是 PID 1，看不到宿主进程 │
│   Network ns     → 有自己的 localhost/端口/IP         │
│   Mount ns       → 有自己的根文件系统（所以 localhost  │
│                   是容器自己，3.4 的坑由此而来）        │
├─────────────────────────────────────────────────────┤
│ cgroup：我最多用这么多 —— 隔离「资源配额」             │
│   cpu / memory 子系统 → 容器 -m 512m 限制的是 cgroup  │
│   （4.4 讲 JVM 如何感知它）                           │
├─────────────────────────────────────────────────────┤
│ overlayfs：镜像分层 + 写时复制（COW）                  │
│   镜像各层只读叠加 → 容器启动只加一个可写顶层          │
│   容器内写文件 = 复制到顶层，不改底层（分层缓存的原理） │
└─────────────────────────────────────────────────────┘
```

**为什么这套设计带来可复现与省空间**：镜像的每一层是只读的，多个容器/多个镜像共享相同底层时磁盘只存一份（几十个 Java 服务共用同一个 JRE 层）；构建时「基础镜像层不变 → 直接命中缓存」就是 3.3 分层 jar 依赖层缓存命中的机制基础。**安全边界要注意**：namespace 是「隔离视图」不是「安全沙箱」，容器逃逸（利用内核漏洞突破 namespace）是真实攻击面——这正是 3.3 坚持非 root、坚持最小镜像的原因（缩小逃逸后的可利用面）。

### 4.2 镜像分层与可复现构建：把「当时的环境」变成「可重建的产物」

一个镜像 = 一串只读层的堆叠 + 一份配置（启动命令、环境变量等），`docker image history` 能看到每一层对应 Dockerfile 的一步。可复现构建的完整链条是：**同一份 Dockerfile + 同一组依赖版本 → 每次构建出行为一致的镜像**。Java 侧的三个破坏可复现的点与对策：

| 不可复现来源 | 为什么漂移 | 对策 |
|------------|----------|------|
| 基础镜像 `latest` 标签 | `latest` 随时间变（基础镜像作者更新） | 固定 tag（`eclipse-temurin:17-jre-jammy`）甚至 digest |
| Maven 依赖不锁版本 | `RELEASE`/区间版本每次解析不同 | 全部固定精确版本 + `mvn wrapper` 锁 Maven 版本 |
| 构建时拉最新代码 | 构建时间不同代码不同 | CI 里用 Git SHA 触发，镜像 tag = 代码提交 |

**为什么这些细节值得写进清单**：「昨天能跑今天不能」的绝大多数根因不是代码变了，而是**构建的输入漂移了**——基础镜像变了、依赖版本解析变了、代码引用变了。可复现 = 可回滚（3.12 的地基）：只有知道「1.4.2 这个镜像确切由什么构建而来」，才能放心 rollback 到它。**多阶段构建（3.3）还顺带解决可复现的另一面**：builder 阶段与运行阶段完全隔离，运行镜像不包含任何「构建时才需要的东西」，镜像内容少到可审计。

### 4.3 Kubernetes 控制面：声明式期望状态背后的控制循环

K8s「你声明要 3 个副本，它保证永远有 3 个」是怎么做到的——答案是**控制循环（reconcile loop）**：一个组件不断把「现实状态」与「期望状态」比对，有偏差就采取动作收敛：

```text
kubectl apply myapp.yaml
   │  期望状态写入
   ▼
┌────────────────────────────── 控制面 ──────────────────────────────┐
│ etcd                ← 集群真相源：所有期望状态/现实状态都存在这      │
│ API Server          ← 唯一入口：所有读写经它（你只跟它说话）         │
│ Controller Manager  ← Deployment 控制器：比对 replicas 期望 vs 现实 │
│                       （现实不足 → 调 API 创建 Pod）               │
│ Scheduler           ← 为新 Pod 挑一个节点（看资源/约束）            │
└─────────────────────────────────────────────────────────────────────┘
                              │ 下发 Pod 定义
                              ▼
┌────────────────────────────── 数据面（每个节点） ───────────────────┐
│ kubelet            ← 节点上的「小控制面」：确保本节点的 Pod 按声明运行 │
│   └─ 定期执行三类探针（3.5）→ readiness 失败就摘出 Service 端点       │
│   └─ 容器 Runtime（containerd）→ 真正拉镜像、起容器                  │
└─────────────────────────────────────────────────────────────────────┘
```

**为什么调度要分离「控制面 vs 数据面」**：控制面（etcd/API/controller/scheduler）是集群的大脑，数据面（每节点的 kubelet+runtime）是手脚——任何节点宕机只影响它上面的 Pod（控制器会在别的节点补副本），大脑不依赖某个具体节点存活。**理解控制循环后，3.5 的清单就全活了**：Deployment 控制器管副本数收敛、探针是 kubelet 的本地判断、Service 的 endpoint 列表由「就绪的 Pod」实时维护——滚动更新/自愈/回滚都是同一个「比对期望与现实」机制的三个具体场景，不需要任何魔法。

### 4.4 JVM 在容器内的内存感知：为什么只配 `-Xmx` 会出事

JVM 的内存行为默认是为「整台物理机」设计的，放进容器后必须让它**感知 cgroup 限制**（4.1），否则会踩两个经典的坑：

| 坑 | 表现 | 原因 |
|----|------|------|
| 堆上限无视容器限制 | 容器 `-m 512m`，JVM 仍按宿主内存比例划堆 → OOMKilled | 老 JDK 读 `/proc/meminfo`（宿主内存）而非 cgroup |
| 显式 `-Xmx` 写死 | 容器从 1g 调到 2g，堆还是 512m（不随配额走）；或反过来 `-Xmx` 设 3g 超过容器 2g → 直接 OOMKilled | `-Xmx` 是固定值，与运行时配额脱节 |

现代 JDK 的解法是**默认开启容器感知**（JDK 8u191+ 可回移植，JDK 10+ 默认 `UseContainerSupport`），配合比例参数而非固定值：

```bash
# 3.3 Dockerfile 里那行 ENTRYPOINT 的为什么：-XX:MaxRAMPercentage 让「堆上限 = 容器可用内存 × 75%」
java -XX:MaxRAMPercentage=75.0 -jar /app/app.jar
```

**为什么是 75% 而不是 100%**：JVM 的内存 = 堆 + 堆外（元空间 Metaspace、JIT 代码缓存、线程栈、直接内存 Direct Buffer、GC 结构）。只把容器配额全给堆，堆外内存仍要空间，总量必然超过容器限制被 OOMKilled。**留 25% 给堆外**是社区经验起步值——容器配额定了，JVM 总量就被约束在配额内；这也解释了为什么 3.4 的 compose 与 3.5 的 k8s 清单里 `mem_limit`/`resources.limits.memory` 必须和 `MaxRAMPercentage` 成对出现：**容器限制是「硬墙」，JVM 参数是「在墙内怎么分配」**，两者缺一，另一个就失真。CPU 同理（`limits.cpu` 会反映进 `Runtime.availableProcessors()` 与 GC 线程数），但因为 GC 线程数只在 JVM 启动时按当时可用核数决定，**CPU 配额改了要重启 JVM 才生效**——扩核 ≠ 改个数字就完事。

## 5. 使用场景

- **部署形态选型（本阶段场景主线）**：先看清「从裸 jar 到 K8s」每一档解决什么问题，再决定当前阶段用哪档——**档位不是越高越好，而是「复杂度 ≤ 收益」**：

| 场景特征 | 部署档位 | 本阶段对应 |
|---------|---------|-----------|
| 学习/单机运行、一个 jar 一个进程 | 裸 jar + nohup/systemd | 3.1、ex07 |
| 服务依赖 MySQL/Redis，本地开发要一键起依赖 | Docker Compose | 3.4、sol-03 |
| 单机演示一个完整应用（含依赖） | Docker + Compose 起整套 | 3.3/3.4、sol-02/sol-03 |
| 多实例、需要自动扩缩容/自愈/滚动发布 | Kubernetes | 3.5/3.6、sol-04 |
| 多环境（dev/staging/prod）重复部署同一服务 | Helm 参数化 | 3.6 |
| 每次提交都要验证并发布 | GitHub Actions 流水线 | 3.8、ex06 |
| 面向真实用户的线上服务 | 上面全部 + 探针/优雅停机/监控/灰度回滚 | 3.5~3.12 |

- **什么时候不该用容器/K8s**：单机批处理/定时任务（cron 或 systemd timer 更简单）；强依赖本地资源与特殊内核模块的软件（容器隔离反而添乱）；只有一两个服务且永远不扩容的小项目——裸 jar + systemd 的运维负担远小于维护一套 K8s。**引入容器 = 引入镜像构建与层缓存的心智，引入 K8s = 引入控制面/网络/存储三套新复杂度**——没到多实例、没到需要自动发布，就别上 K8s。

- **配置外置的分层注入顺序（贯穿 3.2/3.4/3.5/3.6 的一张总图）**：镜像只含「jar + JVM 参数」；环境差异从外向内注入——开发用 `application-dev.yml`，compose 用 `environment:`，K8s 用 ConfigMap，Helm 用 `values.yaml`。**哪一层放什么**：镜像放「不随环境变的」（代码、JVM 参数）、平台放「环境相关的」（数据源地址、密钥、副本数）。Secret 只进 K8s Secret/CI Secret，绝不进镜像与 git。

- **日志与监控的部署分界**：应用只做三件事——JSON 结构化日志打 stdout、暴露 `/actuator/health/*`、暴露 `/actuator/prometheus`；采集（Agent/存储）、检索（ES/Loki）、告警（Alertmanager）全部是平台层。**判断是否越界的一句话**：你的应用代码里出现「写日志文件」「发告警邮件」「读 Prometheus 配置」中的任何一个，就是越界了。

- **跨语言对比（为 analysis/ 与 Tenet 合成积累素材）**：部署层的平台概念（容器/K8s/探针/流水线）是语言无关的，真正的分水岭在 **JVM 的部署形态与 Go 静态二进制**：Go 编译出单个静态二进制 + distroless/scratch 镜像可以小到 10~20 MB、无运行时启动开销、容器内无需任何内存比例参数（Go 的 GC 自动感知 cgroup）；Java 的可执行 jar 几十 MB、运行镜像含 JRE 普遍 200 MB+、JVM 冷启动秒级、还要 `MaxRAMPercentage` 这类容器内存心智。**Java 的追赶方向**是 GraalVM Native Image（把字节码 AOT 编译成原生镜像，体积与启动接近 Go，但反射/动态代理生态受限）与 CDS（Class Data Sharing）——这些属 ph20 的 JVM 深水区，本阶段只需知道「fat jar + JRE 镜像」是 Java 的默认部署形态及其代价来自 JVM 运行时本身。Rust/C++ 与 Go 同属静态二进制阵营，镜像更小但生态更薄；部署链路的模板（examples/ex04~ex07）换语言只换镜像内容与启动命令，平台部分几乎不动。

- **ph18 秒杀 demo 的上生产路径（ph18 预告兑现）**：ph18 的 project 是单 JVM 语义版（三个模拟后端：内存 Redis/内存 L2/假 DB）。把它变成可部署服务 = ① 把模拟后端换成真 Redis/MySQL（坐标见 ph18 examples/ex01）；② 用本阶段 project 的部署模板套上——写 `pom.xml`（3.2 打包）→ 写 Dockerfile（3.3 镜像）→ 用 compose 起 Java+MySQL+Redis（3.4，redis 存库存/锁、mysql 落订单）→ 把 `/actuator/health` 与优雅停机配好（3.11）→ 流水线自动构建镜像（3.8）。**语义层（ph18）与部署层（本阶段）是正交的两层**：秒杀的并发正确性不因部署形态而变，部署的正确性（可复现/可回滚/可观测）也不依赖业务逻辑。

## 6. 代码示例

> 完整可运行版在 [`examples/`](./examples/)（七个示例目录）。验证环境：OpenJDK 17.0.18（Homebrew）+ Spring Boot 3.3.0/Maven 3.9（pom 基线）；**本机无 docker/mvn/helm/kubectl**。ex01（纯 Java 健康检查/JSON 结构化日志/优雅停机）与 ex02 的 jar 结构检查工具已本机实测标注「已验证」；依赖 Spring/Maven 的完整工程与 Docker/Compose/K8s/Helm/GitHub Actions 配置文件标注「未在本环境验证」或「未在本环境实际构建验证」，各文件头给出可复现命令。练习参考实现（sol-01~04）在 [`exercises/`](./exercises/)，项目在 [`project/`](./project/)。

```java
// examples/ex01-healthcheck-logging/ex01-healthcheck-logging.java —— 健康端点 + JSON 日志 + 优雅停机（已验证：OpenJDK 17.0.18 实测）
// 用 JDK 自带 HttpServer 模拟「Spring Boot 可观测三件套」：/actuator/health、JSON 日志行、SIGTERM 优雅停机
server.createContext("/actuator/health", ex -> {
    String body = "{\"status\":\"UP\",\"components\":{\"db\":{\"status\":\"UP\"}}}";
    byte[] out = body.getBytes(StandardCharsets.UTF_8);
    ex.sendResponseHeaders(200, out.length);          // 200 + JSON：这就是探针/健康检查吃的协议
    try (var os = ex.getResponseBody()) { os.write(out); }
});
```

```yaml
# examples/ex04-k8s-manifests/deployment.yaml —— Deployment + 三类探针 + 资源上限（未在本环境实际构建验证）
# readiness 失败 → 摘流量不杀；liveness 失败 → 杀容器重启；startupProbe 给慢启动留 60s 宽限（3.5/3.11 语义）
```

```yaml
# examples/ex06-github-actions/.github/workflows/ci.yml —— build → test → image → deploy 四步流水线（未在本环境实际构建验证）
# 三道 Job 门禁：测试绿才推镜像、镜像推成功才碰集群、deploy 只在 main 分支 environment=prod 且可挂人工审批（3.8）
```

### 示例 1：健康检查 + 结构化日志 + 优雅停机（[`examples/ex01-healthcheck-logging/`](./examples/ex01-healthcheck-logging/)）

纯 Java（JDK 自带 `com.sun.net.httpserver`），用零依赖实现可观测三件套：`/actuator/health` 返回 UP 语义、JSON 行日志、SIGTERM/SIGINT 优雅停机（先拒新连接 → 等存量请求完成 → 超时兜底）。对应主文档 3.9/3.11 的「应用侧最小自检」，**已验证**（OpenJDK 17.0.18 实测）。

### 示例 2：Spring Boot 打包配置 + jar 结构检查器（[`examples/ex02-spring-boot-jar-packaging/`](./examples/ex02-spring-boot-jar-packaging/)）

可执行 jar 的 `pom.xml`（repackage + 分层开关）、`application.yml`（探针/优雅停机/指标端点）。内含一个纯 Java 的 **JarLayersInspector** 工具：传入任意 jar 即列出其 `BOOT-INF/layers.idx` 分层（演示 fat jar 结构教学用）——该工具**已验证**，`mvn package` 打包环节**未在本环境验证**（无 mvn）。

### 示例 3：Dockerfile + Compose 配置集（[`examples/ex03-dockerfile-compose/`](./examples/ex03-dockerfile-compose/)）

多阶段 Dockerfile（分层 jar 按层 COPY / 非 root / HEALTHCHECK）、`docker-compose.yml`（Java + MySQL 8 + Redis 7，健康依赖与数据卷）、`.dockerignore`。配置文件类，**未在本环境实际构建验证**，验证命令见文件头与 examples/README。

### 示例 4：Kubernetes 清单（[`examples/ex04-k8s-manifests/`](./examples/ex04-k8s-manifests/)）

Deployment（滚动策略/三类探针/resources/preStop）+ Service + ConfigMap + Secret + HPA。**未在本环境实际构建验证**，验证命令 `kubectl apply --dry-run=client -f` / `kubectl rollout status`。

### 示例 5：Helm Chart（[`examples/ex05-helm-chart/`](./examples/ex05-helm-chart/)）

Chart.yaml + values.yaml + templates（deployment/service/configmap）+ 多环境 values。**未在本环境实际构建验证**，验证命令 `helm lint` / `helm template` / `helm install`。

### 示例 6：GitHub Actions 流水线（[`examples/ex06-github-actions/`](./examples/ex06-github-actions/)）

`.github/workflows/ci.yml`：build → test → image（GHCR 不可变 tag）→ deploy（helm upgrade + environment 门禁）。**未在本环境实际构建验证**，验证方式是推送到真实仓库观察 Actions 运行。

### 示例 7：Shell 部署脚本集（[`examples/ex07-script-deploy/`](./examples/ex07-script-deploy/)）

deploy.sh（构建 → 上传 → systemd 重启 + 探活）、health-check.sh、rollback.sh、myapp.service unit。脚本语法已用本机 `bash -n` 校验通过；**面向 Linux systemd 的实际执行未在本环境验证**。

## 7. 总结

### 关键要点

- **DevOps 是把部署变成可自动化、可测量、可回滚的开发活动**：CAMS/CALMS 是其价值观，容器/K8s/流水线是其技术落地
- **部署形态四代演进各解决一个痛点**：WAR（统一容器）→ fat jar（自带容器）→ 分层 jar（镜像缓存友好）→ 容器镜像 + K8s（可复现 + 声明式编排）；四代今天仍并存，按场景选档（5 章）
- **镜像构建要可复现**（roadmap 必会概念）：固定基础镜像 tag/依赖版本/Git SHA 触发，不可变 tag 打镜像；可复现才可回滚
- **配置与代码分离**（roadmap 必会概念）：jar/镜像只含代码，环境差异从外注入（命令行/env/ConfigMap/values.yaml），Secret 永不进镜像与 git
- **服务需要健康检查**（roadmap 必会概念）：三类探针语义不混——startup 等慢启动、readiness 摘流量、liveness 杀容器；DB 故障只影响 readiness 不影响 liveness
- **发布必须可回滚**（roadmap 必会概念）：滚动/蓝绿/金丝雀按风险选，回滚路径默认存在（`kubectl rollout undo`/`helm rollback`），触发信号是监控指标不是人肉报告
- **优雅停机与探针合起来才是零停机发布**：SIGTERM → 拒新连接 → 等存量 → 超时兜底；preStop sleep 给流量摘除留缓冲
- **容器里配 JVM 内存用比例不用写死**：`-XX:MaxRAMPercentage=75` + 容器 mem_limit 成对出现，理解堆外内存为什么占 25%
- **应用只做四件事，其余归平台**：JSON 日志打 stdout、暴露健康端点、暴露指标端点、读外置配置——采集/存储/告警都是平台层的横切职责

### 阶段验收清单

- [ ] 能说出裸 jar + systemd、Docker + Compose、K8s + Helm 三档部署各自的适用场景与选择理由（5 章）
- [ ] 能解释 Spring Boot 可执行 jar 的结构（BOOT-INF/lib 为什么存在、JarLauncher 干什么）与分层 jar 为什么让镜像构建变快
- [ ] 能默写一份多阶段 Dockerfile 并说出每一条最佳实践（多阶段/分层 COPY/非 root/HEALTHCHECK）解决什么问题
- [ ] 能写出 Java + MySQL + Redis 的 Compose，说清 `condition: service_healthy` 与命名卷为什么必要
- [ ] 能画出 K8s 控制循环图，解释 Deployment 滚动更新 + 三类探针如何实现自愈与零停机发布
- [ ] 能说出 ConfigMap/Secret/values.yaml 三个配置外置载体各自该放什么
- [ ] 能写一条 GitHub Actions 流水线（build → test → image → deploy）并解释 Job 门禁的作用
- [ ] 能配置 JSON 结构化日志与 Actuator/Prometheus 指标端点，说清应用与采集平台的职责边界
- [ ] 能解释优雅停机时序（SIGTERM → 拒新 → 等存量 → 超时兜底）与 liveness/readiness/startup 的语义差异
- [ ] 能说出滚动/蓝绿/金丝雀的取舍、回滚的标准动作，以及「不可变 tag」为什么是回滚的前提
- [ ] 能解释 `-XX:MaxRAMPercentage=75` 与容器内存限制必须成对的原因（堆外内存）

### 跨语言对比

- 部署平台（容器/K8s/流水线/探针）语言无关；**差异集中在「部署单元的形态」**：Go/Rust/C++ 是单个静态二进制（镜像可小到十几 MB、无启动运行时），Java 是 fat jar + JRE 镜像（200 MB+、秒级冷启动、容器内要管 JVM 内存比例），Python/Node 是解释器 + 依赖目录。**Java 的追赶方向是 GraalVM Native Image 与 CDS，属 ph20 的 JVM 深水区**；本阶段所有模板（Dockerfile/compose/k8s/流水线）换语言只改镜像内容与启动命令，平台部分零改动——这正是「部署是平台能力、与业务语言解耦」的证据（为 analysis/ 与 Tenet 合成积累素材）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：Spring Boot 打包（练习 1）→ Docker 部署（练习 2）→ Compose 起 Java + MySQL + Redis（练习 3）→ Kubernetes 部署（练习 4），四题对应 roadmap 第 19 节列出的四个练习，且与 examples/ex02~ex04 一一对应。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**Spring Boot 部署模板**（roadmap 推荐项目之一）——把本阶段全部要点收进一套「复制即可用」的部署资产：`pom.xml`（打包配置）+ Dockerfile + docker-compose（Java+MySQL+Redis）+ k8s 清单 + GitHub Actions 流水线；配套一个**纯 Java 参考实现**（用 JDK HttpServer 模拟应用，能真实打出可执行 jar、跑通「启动 → 健康检查 → SIGTERM 优雅停机 → 结构化日志」冒烟自检，已在 OpenJDK 17.0.18 本机验证），让无 Docker 环境也能验收「打包/探活/停机」这条部署主链的语义。建议完成练习后再动手。
- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 的纯 Java 冒烟（`./app-smoke.sh` 全部 PASS）并通过其验收标准

### 下一阶段

[ph20 高级 Java 阶段](../ph20-advanced-java/20-advanced-java.md)——本阶段在容器与探针之外埋了两个 JVM 深水区的入口：`-XX:MaxRAMPercentage` 只回答了「容器配额内怎么分内存」，GC 到底怎么选、堆内外的指标曲线怎么解读、Native Image/CDS 这类部署形态的底层机制，都要回到 JVM 本身；同时 4.3 的调度与 3.11 的优雅停机背后还有并发与状态的精细语义（AQS、JMM）——这些是 ph20 的主题，届时以 roadmap 为准。roadmap 第 21 节的车联网方向则将用本阶段的部署模板承接设备接入服务的交付形态。

