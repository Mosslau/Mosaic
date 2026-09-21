# OceanVerse 第 1 阶段 基础设施部署文档

> 📚 **简称约定**：《接入层设计》= 《../ingest/docs/01-接入层设计-v1.md》｜《GB32960 映射》= 《../ingest/docs/02-GB32960协议规格-v1.md》。

> 适用阶段：第 1 阶段第 1 步——最小可用链路的底座
> 容器运行时：**Rancher Desktop**（moby 引擎，非 Docker Desktop，符合本机策略）
> 一键启动后你将得到：Kafka + ClickHouse + MinIO + EMQX + Grafana + Prometheus + MySQL + Redis 八个组件；
> 实时层另加 **Flink 两容器**（JobManager + TaskManager），挂在 compose **profile `realtime`** 上，
> 用 `docker compose --profile realtime up -d` 启动——基础栈仍是八容器。
>
> **文档结构约定**：正文只写**当前事实**（怎么部署、当前边界、当前判据）；
> "为什么变成现在这样"（历次改动）收在末尾 **§6 附录：修订记录**。

---

## 1. 前置条件

| 项 | 要求 | 检查命令 |
|---|---|---|
| Rancher Desktop | 已安装并运行（1.24.0 已装） | `rdctl start` 或打开 App |
| 容器引擎 | moby/dockerd 就绪 | `docker info` 有输出版本号 |
| Compose | v2+ | `docker compose version` |

**启动 Rancher Desktop**（每次开机后如未自动启动）：

```bash
rdctl start
# 等待就绪（首次约 1~4 分钟）：
until docker info >/dev/null 2>&1; do sleep 5; done && echo "engine ready"
```

---

## 2. 镜像加速器（已配置，仅需了解）

国内直连 Docker Hub 会超时，已在 Rancher Desktop 虚拟机内写入 `/etc/docker/daemon.json`：

```json
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.m.daocloud.io",
    "https://docker.1panel.live",
    "https://hub.rat.dev"
  ]
}
```

> 若以后重置了 Rancher Desktop（factory reset），该文件会被清除，按上面内容重建即可。

---

## 3. 组件清单与访问入口

| 组件 | 角色 | 宿主机入口 | 账号 |
|---|---|---|---|
| Kafka 3.9.1 (KRaft) | 消息总线 | `localhost:19092`（宿主机）/ 容器网内 `kafka:9092` | 无认证（第 1 阶段本地） |
| ClickHouse 25.8 | OLAP serving 层 | HTTP `http://localhost:8123` / native `localhost:9000` | `ov_admin` / `ov_pass_2026` |
| MinIO | 对象存储（第 2 阶段湖仓底座）| S3 API `http://localhost:9001` / 控制台 `http://localhost:9002` | `ov_minio` / `ov_minio_2026` |
| EMQX 5.8 | MQTT Broker（车端长连接接入；dev 明文 + 公网 TLS） | MQTT `localhost:11883`/ TLS `localhost:8883`（一车一密 + ACL）/ Dashboard `http://localhost:18083` | `admin` / `public`（登录后立即改密，或启动前设 `EMQX_DASHBOARD_PASSWORD`） |
| Grafana OSS | 看板 | `http://localhost:3000` | `admin` / `admin` |
| Prometheus | 指标采集（网关 `/metrics`，5s 抓取） | `http://localhost:9090` | 无认证（第 1 阶段本地） |
| MySQL 8.4 | 关系库（Java 微服务 ×5 的底座） | `localhost:13306`（避让本机/公司 3306） | `root` / `ov_root_2026`；应用账号 `ov_app` / `ov_app_2026`，库 `oceanverse` |
| Redis 7 | 缓存| `localhost:16379` | 无认证；`maxmemory 192mb` + `allkeys-lru`（`mem_limit 256m`） |

---

## 4. 启动 / 停止 / 重置

```bash
cd deploy

# ⚠️ 首次启动前置：生成自签 CA 与 EMQX 服务器证书（8883 TLS 监听器需要）
bash emqx/gen-certs.sh

# 启动（首次会拉取镜像，约 1.5GB，视网络 5~20 分钟）
docker compose up -d

# 第 1 阶段第 3 步：另起 Flink（JobManager + TaskManager，session cluster）
# 首次会构建 oceanverse/flink:1.20.5（官方镜像不含连接器，构建时补 3 个 jar，见 flink/Dockerfile）
docker compose --profile realtime up -d

# 查看状态（healthy 即就绪）
docker compose ps

# 看日志（排查用）
docker compose logs -f kafka
docker compose logs -f clickhouse
docker compose logs -f minio
docker compose logs -f mysql
docker compose logs -f redis
docker compose logs -f grafana

# 改完 prometheus 的配置/规则后**必须热载**：规则文件是 bind mount，改完文件立刻是新的，但 Prometheus 只在启动时读它 —— 不 reload 则新规则不生效。
curl -X POST localhost:9090/-/reload      # 热载（compose 已加 --web.enable-lifecycle）

# 停止（数据保留在 volume 里，含 Kafka：已显式 KAFKA_LOG_DIRS=/var/lib/kafka/data）
docker compose down

# 完全重置（⚠️ 删除所有数据）
docker compose down -v
```

---

## 5. 启动后验证（逐组件确认）

```bash
# ① Kafka：建一个测试 topic 并自检
docker exec ov-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic ov-smoke-test --partitions 1 --replication-factor 1
docker exec ov-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
# 期望输出包含: ov-smoke-test

# ② ClickHouse：HTTP ping + 查询
curl -s http://localhost:8123/ping        # 期望: Ok.
curl -s "http://ov_admin:ov_pass_2026@localhost:8123/?query=SELECT%20version()"    # 期望输出: 25.8.x

# ③ MinIO：健康检查 + 控制台
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:9001/minio/health/live   # 期望: 200
open http://localhost:9002   # 控制台, ov_minio / ov_minio_2026 登录

# ④ Grafana：健康检查 + 数据源
curl -s http://localhost:3000/api/health   # 期望: {"database":"ok",...}
open http://localhost:3000   # admin / admin 登录
# 期望: 数据源自动出现 "ClickHouse" 与 "Prometheus"(uid=ov-prometheus); 面板应有三个(网关/codec/实时指标)

# ⑤ EMQX：状态 + Dashboard
curl -s http://localhost:18083/status    # 期望: "Node emqx@127.0.0.1 is started" + "emqx is running"(非字面 "ok")
open http://localhost:18083              # admin / public 登录(建议立即改密)
docker exec ov-emqx emqx ctl listeners | grep -E "tcp:default|ssl:default"
# 期望: Dashboard → 集成 → 规则 应有 ov_vehicle_ingress 与 ov_binary_ingress 两条

# ⑥ Prometheus：抓取目标 + 网关指标(需网关已在宿主机运行)
curl -s 'http://localhost:9090/api/v1/targets?state=active' | grep -o '"health":"[a-z]*"' # 期望: "health":"up"; 网关未启动时显示 down 属正常
curl -s -g 'http://localhost:9090/api/v1/query?query=up{job="device-gateway"}' # 告警规则已加载
curl -s http://localhost:9090/api/v1/rules | grep -c '"name"'    # 期望: 15
curl -s http://localhost:9090/api/v1/alerts | grep -c '"state":"firing"' || true   # 期望: 0
docker exec ov-prometheus promtool test rules /etc/prometheus/rules/tests/flink-checkpoints.test.yml

# ⑦ MySQL：ping + 库存在(只建库不建表, 故查 information_schema 应为空)
docker exec ov-mysql mysqladmin ping -h 127.0.0.1 -u root -pov_root_2026   # 期望: mysqld is alive
docker exec ov-mysql mysql -u root -pov_root_2026 -e "SHOW DATABASES LIKE 'oceanverse';" 
docker exec ov-mysql mysql -u root -pov_root_2026 -e "SELECT COUNT(*) AS tables_now FROM information_schema.tables WHERE table_schema='oceanverse';"   # 期望: 库存在, tables_now = 0

# ⑧ Redis：ping + 内存上限确实生效(这条是防"整机被缓存吃穿"的关键)
docker exec ov-redis redis-cli ping                                        # 期望: PONG
docker exec ov-redis redis-cli config get maxmemory                        # 期望: 201326592 (192mb)
docker exec ov-redis redis-cli config get maxmemory-policy                 # 期望: allkeys-lru

# ⑨ Flink（第 3 步；需已用 --profile realtime 启动）
curl -s http://127.0.0.1:18088/overview   # 期望含 "taskmanagers":1 与 "slots-available":3
docker compose --profile realtime ps      # 期望 ov-flink-jm / ov-flink-tm 均 healthy

# ⑨.1 检查点配置**真的生效**了吗（只看配置文件会被骗: 作业级配置只在提交端生效, 集群侧只是默认值）
docker exec ov-flink-jm sh -c 'grep -A4 "checkpointing:" /opt/flink/conf/config.yaml'
docker exec ov-flink-tm sh -c 'grep -A5 "^s3:" /opt/flink/conf/config.yaml'   # TM 才是上传状态的一方
```

---

## 6. 附录：修订记录

> 这里按时间记录"为什么变成现在这样"；正文（§1–§5）只写当前事实。

| 日期 | 改了什么 | 为什么 |
|---|---|---|
| 2026-09-16 | 初版：Kafka / ClickHouse / MinIO / Grafana 四组件 + 镜像加速器 + 端口避让 | 最小可用链路底座 |
| 2026-09-16 | MQTT 压测改到容器网内进行 | 宿主→VM→容器转发层并发 ≈185 连接/端口 |
| 2026-09-17 | +EMQX / +Prometheus；EMQX 明文宿主端口 1883→11883 | 接入车端 MQTT；本机 RabbitMQ MQTT 插件抢占 1883 |
| 2026-09-18 | Kafka 数据显式入卷（KAFKA_LOG_DIRS）；全服务 `restart: unless-stopped` + `mem_limit` + 日志轮转；宿主端口统一 `127.0.0.1` 回环绑定 | 此前 down+up 会丢全部 topic 与位移；引擎重启后链路静默下线；弱口令组件不能暴露给同网段 |
| 2026-09-18 | +MySQL / +Redis（只建库不建表） | 第 4 步 Java 微服务的底座 |
| 2026-09-18 | 八容器 `mem_limit` 合计 6.88 GiB 超 VM 实测量（6.2 GiB）→ 整体压回 + ClickHouse 进程内上限落 `limits.xml` 并挂进容器 | 上限之和超物理内存 = 整机 OOM 风险 |
| 2026-09-18 | Prometheus 告警规则从无到有 | VM 掉线导致链路停摆而监控无人知晓 |
| 2026-09-20 | MinIO 镜像改 `quay.io/minio/minio`（digest 与 Docker Hub 一致） | Docker Hub 已拒绝匿名拉取，CI 干净环境首跑才发现 |
| 2026-09-20 | Rancher VM 6→8 GB；按实测用量重分配（ClickHouse 1280m→2560m，合计 6656 MiB） | CH 进程内上限余量不足 → "活着但干不了活" |
| 2026-09-20 | Flink 入栈：自建镜像 `oceanverse/flink:1.20.5`（补连接器 jar）、profile `realtime`、宿主端口 18088 | 第 3 步实时作业；官方镜像不含连接器；8081 被公司 Java 服务占 |
| 2026-09-20 | Flink 告警 5 条补齐（规则总数 15）+ promtool 规则语义单测进 CI | 实时层此前零指标零告警；检查点类规则曾出现残留 series 假阳性 |
| 2026-09-20 | Prometheus 规则热载纪律：`--web.enable-lifecycle` + 改后必须 `/-/reload` | 规则文件是 bind mount，改完不 reload 则新规则不生效 |
| 2026-09-20 | P1 配置：检查点落 MinIO（镜像自带 s3 插件）、位点 `group-offsets`、sink exactly-once、作业级配置改到提交端（`CLIENT_FLINK_PROPERTIES`）、TM 补 `s3.*`、`FLINK_PROPERTIES` 只许 `key: value` | 检查点/位点/幂等落地过程中连踩四个静默配置坑 |
| 2026-09-20 | Q&A runbook 整节移除（原 Q1–Q25）：可机械化的判据已沉淀进门禁与脚本（`check-pipeline-health.sh` 的失败提示自带处置、compose/规则文件注释自包含），"为什么"保留在本附录 | 文档约定收口为"正文只写当前事实、不要解释"；排障知识以"门禁+脚本"形式存在，不再单设章节 |
| 2026-09-20 | 配置文件注释瘦身：compose 文件头叙事收编为"四条纪律"、删除过期事实（VM 内存数、规则计数、MinIO"未入链路"等）与各服务调整史；alerts 文件头压缩。Dockerfile/emqx.conf 的注释评估为**不冗余**（坑的唯一载体），未动 | 与文档同一约定：解释只写一遍；配置文件注释只留"防重踩"的约束与理由 |
| 2026-09-20 | 本文档结构整理：正文=当前事实，历史叙事收进本附录 | 补丁式留痕多轮后阅读成本过高 |
| 2026-09-20 | 修 §5 ⑨ Flink 块**丢失开围栏**的渲染错位（`# ⑨` 被渲染成 H1、后半篇代码/正文反转）；全仓 39 处无标签围栏补 ` ```text `；`check-docs.sh` 新增 ⑪ 围栏健康门禁 | 这类错位不报错、不挂 CI、只在渲染层崩——属"必须机械化"的一类（由渲染页人工发现） |
| 2026-09-20 | §3/§6 瘦身：解释与现场叙事全部删除（§3 字符 -18%、全文 559→467 行），Q&A 每条只留"现象→根因一句话→判据→处置" | 文档约定：**解释只写一遍**（在本附录或 Q&A 的根因行），不复述 |
