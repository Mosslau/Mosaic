# OceanVerse 第 1 阶段 基础设施部署文档

> 📚 **简称约定**：《接入层设计》= 《../ingest/docs/01-接入层设计-v1.md》｜《GB32960 映射》= 《../ingest/docs/02-GB32960协议规格-v1.md》。

> 适用阶段：第 1 阶段第 1 步——最小可用链路的底座
> 容器运行时：**Rancher Desktop**（moby 引擎，非 Docker Desktop，符合本机策略）
> 一键启动后你将得到：Kafka + ClickHouse + MinIO + EMQX + Grafana + Prometheus + MySQL + Redis 八个组件；
> 实时层（第 3 步）另加 **Flink 两容器**（JobManager + TaskManager），挂在 compose **profile `realtime`** 上，
> 用 `docker compose --profile realtime up -d` 启动——基础栈仍是八容器。
>
> **文档结构约定（2026-09-20 起）**：正文只写**当前事实**（怎么部署、当前边界、当前判据）；
> "为什么变成现在这样"（历次改动）收在末尾 **§7 附录：修订记录**；常见问题（§6）只保留"还可能再发生、
> 需要现场处置"的条目，已彻底收口且回归有判据把守的条目折叠进附录（Q 编号不回收，历史引用不受影响）。

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

配置文件位置（主机侧，已创建好，无需再动）：
`~/Library/Application Support/rancher-desktop/lima/_config/override.yaml`

> 若以后重置了 Rancher Desktop（factory reset），该文件会被清除，按上面内容重建即可。

---

## 3. 组件清单与访问入口

| 组件 | 角色 | 宿主机入口 | 账号 |
|---|---|---|---|
| Kafka 3.9.1 (KRaft) | 消息总线 | `localhost:19092`（宿主机）/ 容器网内 `kafka:9092` | 无认证（第 1 阶段本地） |
| ClickHouse 25.8 | OLAP serving 层 | HTTP `http://localhost:8123` / native `localhost:9000` | `ov_admin` / `ov_pass_2026` |
| MinIO | 对象存储（第 2 阶段湖仓底座）；镜像取自 **quay.io**（背景见 §7） | S3 API `http://localhost:9001` / 控制台 `http://localhost:9002` | `ov_minio` / `ov_minio_2026` |
| EMQX 5.8 | MQTT Broker（车端长连接接入；dev 明文 + 公网 TLS） | MQTT **`localhost:11883`**（1883 被本机 RabbitMQ 占用，`.env` 覆盖；克隆后无 `.env` 则为 1883 —— 故事见 Q10，模板见 `.env.example`）/ **TLS `localhost:8883`（一车一密 + ACL，见 Q12）** / Dashboard `http://localhost:18083` | `admin` / `public`（**登录后立即改密**，或启动前设 `EMQX_DASHBOARD_PASSWORD`） |
| Grafana OSS | 看板 | `http://localhost:3000` | `admin` / `admin` |
| Prometheus | 指标采集（网关 `/metrics`，5s 抓取） | `http://localhost:9090` | 无认证（第 1 阶段本地） |
| MySQL 8.4 | 关系库（第 1 阶段第 4 步 Java 微服务 ×5 的底座） | `localhost:13306`（避让本机/公司 3306） | `root` / `ov_root_2026`；应用账号 `ov_app` / `ov_app_2026`，库 `oceanverse` |
| Redis 7 | 缓存（第 2 阶段"限流器 Redis 化"的落点） | `localhost:16379`（避让 6379） | 无认证（第 1 阶段本地）；`maxmemory 192mb` + `allkeys-lru`（`mem_limit 256m`） |

默认数据库：ClickHouse 自动建 `oceanverse` 库，MySQL 自动建 `oceanverse` 库（**只建库不建表**——业务 DDL 归第 4 步各 Java 服务，这里造表是空转）。
Grafana 启动后**自动配好名为 `ClickHouse` 的数据源**（provisioning，见 `deploy/grafana/provisioning/datasources/clickhouse.yaml`）。
EMQX 启动后**自动加载声明式规则**（`deploy/emqx/emqx.conf`）：① `ov_vehicle_ingress` —— `ov/+/status|battery|fault` → Webhook → 网关 `/api/v1/mqtt/ingest`；② `ov_binary_ingress` —— `ov/+/bin`（GB/T 32960 二进制帧，base64）→ 网关 `/api/v1/bin/ingest` → `ov.raw.binary.v1` → device-codec（Dashboard → 集成 → 规则 可见两条）。

> **内存预算（被 `scripts/check-compose-budget.sh` 门禁覆盖，数字不许手改漂移）**：
> Kafka 640m + ClickHouse 2560m + MinIO 192m + MySQL 512m + Redis 256m
> + EMQX 384m + Prometheus 256m + Grafana 320m + flink-jobmanager 512m + flink-taskmanager 1024m
> = **6656 MiB**，占本机 VM 容量（7934 MiB）的 **84%**（门禁要求合计 ≤ 85%：**预留已用满**；
> 再加容器或调大额度必须重算、写明理由、并同步门禁的预算默认值）。
>
> 三条配套纪律：
> ① **进程内上限 < cgroup 硬杀线，且显著高于进程地板**：ClickHouse 上限（1536 MiB）写在
>    `clickhouse/config.d/limits.xml` 且**必须挂进容器**（环境变量无效，实测）；缓存上限必须显式声明
>    （镜像默认 mark/index_mark 各 5 GiB、uncompressed 8 GiB，在小上限下会与查询抢额度）。
>    Redis / Flink 同理：`--maxmemory 192mb` < `mem_limit 256m`；`process.size` 448m/896m <
>    `mem_limit` 512m/1024m。为什么必须这样（地板 ≈850 MiB、RSS 滞留爬升、越限后 OvercommitTracker
>    拒查询 = "活着但干不了活"）见 Q17。
> ② **改 limits 后必须复跑门禁**：`bash scripts/check-compose-budget.sh`（CI 也跑）；
>    判据明细见脚本头注与 `scripts/README.md`。
> ③ `bash scripts/test-compose-budget.sh` 是门禁自身的负向对照（改数字必须变红）。

> 两个说明：① 端口避让 —— MinIO 的 S3 API 映射到宿主 `9001`、控制台 `9002`，因为 ClickHouse native
> 已占 `9000`；② MinIO 镜像取自 **quay.io** —— Docker Hub 的 `minio/minio` 已拒绝匿名拉取，
> 两者 digest 一致（背景见 §7；拉不动时的换源打法见 Q3）。

---

## 4. 启动 / 停止 / 重置

```bash
cd deploy

# ⚠️ 首次启动前置：生成自签 CA 与 EMQX 服务器证书（8883 TLS 监听器需要）
bash emqx/gen-certs.sh
#   不跑会怎样：EMQX 仍能启动、dev 明文 1883 正常，但 8883 TLS 监听器因缺证书不可用
#   （容器日志出现 cert_file_not_found: /opt/emqx/etc/certs/server.crt），
#   且公网三件套自检（Q12）第 ① 项会直接失败。证书目录已 gitignore，克隆后必须自己生成。

# 启动（首次会拉取镜像，约 1.5GB，视网络 5~20 分钟）
docker compose up -d

# 第 1 阶段第 3 步：另起 Flink（JobManager + TaskManager，session cluster）
#   首次会构建 oceanverse/flink:1.20.5（官方镜像不含连接器，构建时补 3 个 jar，见 flink/Dockerfile）
docker compose --profile realtime up -d
#   UI: http://127.0.0.1:18088 —— 期望 Overview: Task Managers = 1, Available Task Slots = 3
#   注意用 127.0.0.1 而不是 localhost: 本机 localhost 优先解析成 ::1, 而 8081 被公司 Java 服务占着(Q18)

# 查看状态（healthy 即就绪）
docker compose ps

# 看日志（排查用）
docker compose logs -f kafka
docker compose logs -f clickhouse
docker compose logs -f minio
docker compose logs -f mysql
docker compose logs -f redis
docker compose logs -f grafana

# 改完 prometheus 的配置/规则后**必须热载**：规则文件是 bind mount，改完文件立刻是新的，
#   但 Prometheus 只在启动时读它 —— 不 reload 则新规则不生效（背景见 §7 修订记录）。
curl -X POST localhost:9090/-/reload      # 热载（compose 已加 --web.enable-lifecycle）
#   判据: curl -s localhost:9090/api/v1/rules | python3 -c "import json,sys;d=json.load(sys.stdin)['data']['groups'];print(sum(len(g['rules']) for g in d))"
#   应与规则文件里的 alert 条数一致；也可直接跑 bash scripts/check-pipeline-health.sh（判据 6 就是这条）。
#   其它容器（EMQX/Grafana/ClickHouse/MySQL/Redis）的配置改动仍需重启对应容器：docker compose up -d <服务名>

# 停止（数据保留在 volume 里，含 Kafka：已显式 KAFKA_LOG_DIRS=/var/lib/kafka/data）
docker compose down

# 完全重置（⚠️ 删除所有数据）
docker compose down -v
```

---

## 5. 启动后验证（逐组件确认）

```bash
# ① Kafka：建一个测试 topic 并自检
docker exec ov-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --if-not-exists --topic ov-smoke-test --partitions 1 --replication-factor 1
docker exec ov-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
# 期望输出包含: ov-smoke-test

# ② ClickHouse：HTTP ping + 查询
curl -s http://localhost:8123/ping        # 期望: Ok.
curl -s "http://ov_admin:ov_pass_2026@localhost:8123/?query=SELECT%20version()"
# 期望输出: 25.8.x

# ③ MinIO：健康检查 + 控制台
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:9001/minio/health/live   # 期望: 200
open http://localhost:9002   # 控制台, ov_minio / ov_minio_2026 登录

# ④ Grafana：健康检查 + 数据源
curl -s http://localhost:3000/api/health   # 期望: {"database":"ok",...}
open http://localhost:3000   # admin / admin 登录
# 左侧 Connections → Data sources → 应看到两个数据源: "ClickHouse" 与 "Prometheus"(uid=ov-prometheus)
# 左侧 Dashboards → 应看到三个面板:
#   "device-gateway 车端接入网关" (请求速率/延迟分位/受理vsKafka对账/在途)
#   "device-codec 编解码服务"     (消费vs解码/DLQ速率按stage/消费lag/微批耗时与批大小)
#   "realtime 实时指标"           (在线数/在线数趋势/故障按码/高温告警 —— 第 3 步产物)

# ⑤ EMQX：状态 + Dashboard
curl -s http://localhost:18083/status    # 期望: "Node emqx@127.0.0.1 is started" + "emqx is running"(非字面 "ok")
open http://localhost:18083              # admin / public 登录(建议立即改密)
# Dashboard → 集成 → 规则: 应有两条 —— ov_vehicle_ingress(JSON: status/battery/fault)
#                                              与 ov_binary_ingress(二进制: ov/+/bin, base64)
# 监听器: 1883 明文(dev) + 8883 TLS(公网形态, 一车一密+ACL) —— 缺证书时 8883 不可用(见 §4 前置)
docker exec ov-emqx emqx ctl listeners | grep -E "tcp:default|ssl:default"

# ⑥ Prometheus：抓取目标 + 网关指标(需网关已在宿主机运行)
curl -s 'http://localhost:9090/api/v1/targets?state=active' | grep -o '"health":"[a-z]*"'
# 期望: "health":"up"; 网关未启动时显示 down 属正常
curl -s -g 'http://localhost:9090/api/v1/query?query=up{job="device-gateway"}'
# 告警规则已加载且无 firing(15 条告警, 含义见 Q16)
curl -s http://localhost:9090/api/v1/rules | grep -c '"name"'    # 期望: 15
curl -s http://localhost:9090/api/v1/alerts | grep -c '"state":"firing"' || true   # 期望: 0
# 规则**语义**单测(该响/不该响; 曾在运行态出过假阳性, 见 Q25)
docker exec ov-prometheus promtool test rules /etc/prometheus/rules/tests/flink-checkpoints.test.yml

# ⑦ MySQL：ping + 库存在(只建库不建表, 故查 information_schema 应为空)
docker exec ov-mysql mysqladmin ping -h 127.0.0.1 -u root -pov_root_2026   # 期望: mysqld is alive
docker exec ov-mysql mysql -u root -pov_root_2026 -e \
  "SHOW DATABASES LIKE 'oceanverse'; SELECT COUNT(*) AS tables_now FROM information_schema.tables WHERE table_schema='oceanverse';"
# 期望: 库存在; tables_now = 0(业务表属第 4 步各 Java 服务的 DDL)

# ⑧ Redis：ping + 内存上限确实生效(这条是防"整机被缓存吃穿"的关键)
docker exec ov-redis redis-cli ping                                        # 期望: PONG
docker exec ov-redis redis-cli config get maxmemory                        # 期望: 201326592 (192mb)
docker exec ov-redis redis-cli config get maxmemory-policy                 # 期望: allkeys-lru
```

> **端口避让（本机实测）**：公司 Java 服务占用 8080~8083，网关开发期用 `GATEWAY_PORT=18080` 启动；
> `deploy/prometheus/prometheus.yml` 抓取目标与 `deploy/emqx/emqx.conf` webhook url 已对齐 18080（《接入层设计》§5.3 对齐线）。
> 若在 8080 空闲的机器上开发，两处改回 8080 即可。

```bash
# ⑨ Flink（第 3 步；需已用 --profile realtime 启动）
curl -s http://127.0.0.1:18088/overview
# 期望含 "taskmanagers":1 与 "slots-available":3
docker compose --profile realtime ps      # 期望 ov-flink-jm / ov-flink-tm 均 healthy

# ⑨.1 检查点配置**真的生效**了吗（P1；只看配置文件会被骗, 见 Q20）
docker exec ov-flink-jm sh -c 'grep -A4 "checkpointing:" /opt/flink/conf/config.yaml'
docker exec ov-flink-tm sh -c 'grep -A5 "^s3:" /opt/flink/conf/config.yaml'   # TM 才是上传状态的一方(Q22)
```

全部通过后，基础栈就绪；第 3 步的实时作业（在线数 / 故障数 / 高温电池）见《实时计算层设计》与 `lakehouse/warehouse/streaming/`。

---

## 6. 常见问题（runbook）

> 收录规则：只放"**还可能再发生、需要现场处置**"的条目，每条按"现象 → 根因一句话 → 判据 → 处置"写，
> **不复述解释**（"为什么变成现在这样"只在 §7 附录写一遍）；
> 已彻底收口且回归有判据把守的条目折叠进 §7（Q 编号不回收，历史文档里的引用不受影响）。
> 主题索引：

| 主题 | 条目 |
|---|---|
| 环境/镜像拉取 | Q1–Q3、Q5 |
| Grafana/EMQX 接入 | Q6–Q8、Q10、Q12 |
| 压测与端口转发 | Q9、Q14、Q18 |
| Kafka/消费组 | Q11、Q13 |
| 自愈与告警 | Q15、Q16、Q25 |
| ClickHouse 内存 | Q17 |
| Flink | Q18、Q20–Q24 |

**Q1：`docker info` 连不上 daemon**
Rancher Desktop 没启动。`rdctl start`，等 1~4 分钟再试。

**Q2：拉镜像超时 `dial tcp ...:443: i/o timeout`**
镜像加速器未生效。确认 §2 的 `override.yaml` 存在后 `rdctl shutdown && rdctl start`，再 `rdctl shell cat /etc/docker/daemon.json` 确认 mirrors 在里面。

**Q3：拉镜像报 `403 Forbidden`（某镜像站抽风）**
直接重试 `docker compose pull`；仍不行则换镜像站单独拉再重打标签：

```bash
docker pull docker.1ms.run/grafana/grafana-oss:latest
docker tag docker.1ms.run/grafana/grafana-oss:latest grafana/grafana-oss:latest
docker compose up -d
```

**Q5：拉取中途 `unexpected EOF`（网络抖动）**
重试即可，已下载的分层会续传：

```bash
for i in 1 2 3 4 5; do docker compose pull && break || sleep 5; done
```

**Q6：Grafana 数据源没有自动出现**
首次启动需下载 ClickHouse 插件（`GF_INSTALL_PLUGINS`），网络慢时会等较久：看 `docker compose logs -f grafana`，必要时 `docker compose restart grafana`。

**Q7：EMQX Dashboard 里看不到 `ov_vehicle_ingress` 规则**
规则由 `deploy/emqx/emqx.conf` 声明式定义。判据：`docker exec ov-emqx cat /opt/emqx/etc/emqx.conf | grep ov_vehicle_ingress`（没挂上）；`docker compose logs emqx` 看配置解析错误（HOCON 字段名对版本敏感）。兜底：Dashboard → 集成 → 规则 → 手动新建（SQL 和 webhook 参数抄 `emqx.conf` 对应段）。

**Q8：EMQX webhook 转发失败（规则监控里失败计数上涨）**
最常见是 EMQX 容器访问不到宿主机网关（前置：网关已在 18080 启动）。判据：`docker exec ov-emqx wget -qO- http://host.docker.internal:18080/health`。不通则把 `emqx.conf` 里 webhook url 的 `host.docker.internal` 换成 `host.lima.internal` 或宿主机局域网 IP，`docker compose restart emqx`。

**Q9：宿主机跑 MQTT 模拟器，并发连接永远卡 ≈185、`connection reset by peer`**
Rancher 端口转发层（宿主→VM→容器）并发上限 ≈185 连接/端口（裸 socket 实测复现，网内直连正常）。**MQTT 压测改在容器网内跑**：

```bash
# 交叉编译 linux 二进制(静态, 任何镜像可承载)
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -o /tmp/msim-linux ./ingest/device-simulator/cmd/mqtt-simulator
cp /tmp/msim-linux .tmp-msim   # 放 workspace(Rancher 只共享 $HOME 给 VM, /tmp 挂不进)
docker run --rm --network oceanverse_ov-net -v $PWD/.tmp-msim:/msim:ro \
  --entrypoint /msim grafana/grafana-oss:latest \
  -broker tcp://emqx:1883 -devices 5000 -interval 5s -duration 60s
rm .tmp-msim
```

万车档：VM 已提到 8 GB 但该档未复测（《roadmap/项目进度.md》待收口项 #3）；更大档位去专用压测节点。

**Q10：模拟器显示"连接成功/发布成功"，但 EMQX 里一个客户端/一条消息都没有**
连错了 broker：宿主 1883 被 RabbitMQ MQTT 插件占用，模拟器连的是它而不是容器 EMQX。判据：`lsof -nP -iTCP:1883 -sTCP:LISTEN` 看到的不是容器转发进程；`docker exec ov-emqx emqx ctl clients list` 报 No clients。处置：`deploy/.env` 写 `EMQX_MQTT_PORT=11883` 后 `docker compose up -d emqx`；模拟器 `-broker tcp://localhost:11883`。

**Q11：codec/网关重启后消费组不消费（lag 不涨不落、新实例 consumed 恒 0）**
`pkill -f "go run ./cmd/server"` 只杀了 go run 包装进程，**编译产物子进程（exe/server）变孤儿仍占消费组成员位** → 新实例分不到分区。判据：`kafka-consumer-groups.sh --describe --group device-codec-v1 --members` 有多个 member 且持分区者不是当前实例。处置：`pkill -f "exe/server"` 杀干净，等僵尸成员会话超时（~1 分钟）再起单实例。
附带坑：codec 的 `:18090` 也会被旧实例占住（日志 `bind: address already in use`，主流程照跑但 Prometheus 抓不到）——重启前确认 `lsof -nP -iTCP:18090 -sTCP:LISTEN` 为空。本地联调优先 `go build` 出二进制再跑（杀起来干净；生产 K8s 无此问题）。

**Q12：公网路径安全三件套（TLS / 一车一密 / ACL）怎么在本地跑起来**
三步（《接入层设计》§8.3）：

```bash
# ① 生成自签 CA + 服务器证书(仅本地! 生产换正式 CA)
bash deploy/emqx/gen-certs.sh
# ② 重建 EMQX 加载 8883 TLS 监听器 + 监听器级认证 + ACL
cd deploy && docker compose up -d emqx
# ③ 批量灌设备凭证(密码规则 pw-{VIN}, 仅 dev) 并自检八项
bash emqx/seed-users.sh 0 100
cd ../ingest/device-simulator && go run ./cmd/security-check -vin OV20260001
```

退出码：0=八项全过 / 1=安全项不达标 / 3=前置（凭证）不可用。生产形态连 8883：`go run ./cmd/bin-simulator -tls -broker localhost:8883 -cacert ../../deploy/emqx/certs/ca.crt`（clientid/username=VIN）。
两个前提：VIN 必须在已灌范围内（默认灌 `OV00000000..99`；大号 VIN 用 `bash emqx/seed-users.sh --vin OV20260001` 单独灌）；凭证存 mnesia、容器重建不必重灌（compose 已固定 `EMQX_NODE__NAME=emqx@127.0.0.1`，否则换容器 IP 即换空库）。
注意：8883 对外开放前必须完成自检；本地自签证书与 `pw-` 密码规则**不得**用于生产。

**Q13：容器里的服务（网关/codec）写 Kafka 失败，但宿主机跑就正常**
Kafka 双监听器：`PLAINTEXT://kafka:9092`（容器网内）/ `EXTERNAL://localhost:19092`（宿主机）——容器里 `localhost` 指向容器自身。容器一律：

```bash
docker run --network oceanverse_ov-net -e KAFKA_BROKERS=kafka:9092 ...
```

对照：宿主机进程 → `localhost:19092`；容器内进程 → `kafka:9092`（且必须挂 `oceanverse_ov-net`）。

**Q14：为什么宿主端口从 `0.0.0.0` 改成了 `127.0.0.1`？**
底座含弱口令（EMQX/Grafana）与无认证组件（Kafka/Prometheus），绑 `0.0.0.0` 会把它们连同数据暴露给同网段。容器间通信不受影响（走 `ov-net` 服务名），README 里所有 `localhost:xxxx` 命令继续有效。确需局域网访问时临时加一条端口映射即可，别改回全网卡。

**Q15：容器为什么不自己恢复？**
已统一 `restart: unless-stopped` + `mem_limit` + 日志轮转（10m×3），引擎/宿主重启后无需人工干预。验证：

```bash
rdctl shutdown && rdctl start --container-engine.name moby   # 模拟宿主重启
docker compose ps      # 无需任何 up 命令, 期望全部 healthy
```

注：`docker kill ov-kafka` 属**显式停止**，`unless-stopped` 不会拉起（预期行为）；验证自愈要用引擎重启。

**Q16：链路静默停摆怎么第一时间知道？（告警与 runbook）**
15 条规则（`deploy/prometheus/rules/oceanverse-alerts.yml`）：

| 告警 | 触发条件 | 含义 |
|---|---|---|
| `TargetDown` | `up == 0` 持续 1m | 网关/codec/十容器任一掉线（VM 掉线时全部一起 down） |
| `GatewayKafkaWriteErrors` | 网关写 Kafka 失败 >0 | 消息未落盘，已返 5xx 让上游重试 |
| `CodecFlushFailures` | codec 写出/提交失败 >0 | **丢数据之前的第一道信号**（此时数据仍在缓冲） |
| `CodecBufferBacklog` | `pending_messages > 1000` 持续 5m | 下游长时间不可写 |
| `CodecConsumerLag` | `consumer_lag > 5000` 持续 5m | 实时性退化 |
| `CodecDLQGrowing` | DLQ 10 分钟内增长 | 对端字节问题或契约不同步 |
| `GatewayRateLimited` | 5 分钟限流 >100 次 | 容量不足或单设备发疯 |
| `GatewayVINMismatch` | 载荷 VIN ≠ topic VIN | **安全信号**，可能是伪造尝试（HTTP/MQTT 通道） |
| `CodecVINMismatch` | `codec_dlq_total{stage="vin_mismatch"}` 增长 | **安全信号**：二进制帧内 VIN ≠ 信封 VIN（网关不解帧，只能在此拦） |
| `IngestLatencyHigh` | 上行延迟 p99 > 1s 持续 5m | 平台段（webhook→落盘）劣化；EMQX 重投也会如实抬高 |
| `FlinkJobsMissing` | `flink_jobmanager_numRunningJobs < 3` 持续 2m | **实时作业少了**：某个指标停止更新 |
| `FlinkTaskManagerMissing` | 已注册 TM < 1 持续 1m | TM 掉线 → 作业卡在等资源，而 JM 自身仍"健康" |
| `FlinkJobRestarts` | 15 分钟内 `job_numRestarts` 增长 | 作业重启过（已开 checkpoint：重启会从检查点续跑，但仍要留意） |
| `FlinkCheckpointFailures` | 15 分钟内失败检查点 >0 | 恢复能力在退化——作业仍 RUNNING 但重启会退回更早状态 |
| `FlinkCheckpointStalled` | 15 分钟内完成检查点 =0 | 检查点卡住/被跳过（MinIO 不可达、反压） |

> Flink 指标来自自建镜像里的 `flink-metrics-prometheus`：JM/TM 各自暴露 `:9249`（不发布到宿主），
> Prometheus 走容器网直连；抓取失败由通用 `TargetDown` 覆盖。「没有数据」**不设告警**——
> 开发机上没有车在上报同样没有数据，这类"无基线"判据会天天误报。

```bash
curl -s localhost:9090/api/v1/alerts | python3 -c "import json,sys;print('firing:',len(json.load(sys.stdin)['data']['alerts']))"
# 期望: firing: 0
```

**runbook 一行**：`firing > 0` → 先看面板确认范围 → 查 `docker compose ps`（容器）与 `lsof -nP -iTCP:18080 -sTCP:LISTEN`（宿主进程）→ 两者都正常则怀疑 Rancher 端口转发层（Q8）→ 恢复后复跑 `bash scripts/check-pipeline-health.sh` 确认无僵尸消费组。

> **能力边界**：本机**没有 Alertmanager**，告警只出现在 Prometheus UI/API（<http://localhost:9090/alerts>），
> **不会**变成手机/邮件通知——需要主动看，或让面板/巡检脚本看。接 Alertmanager 是第 2 阶段。

**Q17：ClickHouse 查询报 `MEMORY_LIMIT_EXCEEDED`，但 `SELECT 1` 正常（服务活着，却干不了活）**
进程内上限余量不够：进程地板（重启后空闲）≈830~870 MiB；跑久后 RSS 自己爬到 1.1~1.2 GiB（jemalloc 滞留页/碎片）；RSS 越过 `limits.xml` 的 `max_server_memory_usage` 后 OvercommitTracker 拒绝一切要内存的查询。

```bash
docker stats --no-stream --format '{{.MemUsage}} ({{.MemPerc}})' ov-clickhouse
curl -s -G "http://ov_admin:ov_pass_2026@localhost:8123/" --data-urlencode \
  "query=SELECT formatReadableSize(value) FROM system.asynchronous_metrics WHERE metric='MemoryResident'"
# RSS 逼近/超过 limits.xml 里的 max_server_memory_usage（现 1536 MiB）即命中
```

处置：① 止血 `docker compose restart clickhouse`（实测 RSS 1.16 GiB → 830 MiB，被拒查询立即恢复；落表后重启需考虑作业恢复）；
② 治本：`max_server_memory_usage` 显著高于地板（现 1536 MiB）+ 四个缓存上限显式声明 + `mem_limit`（2560m）> 进程内上限 —— 门禁④核对；
③ 仍频繁触发：查 `system.query_log` 的 `memory_usage`（需该表已启用），或按真实规模重新分配。

**Q18：`localhost:8081` 打不开 Flink（HTTP 500），但 `127.0.0.1:8081` 正常**
本机已有 Java 服务监听 IPv6 `*:8081`，macOS 的 `localhost` 优先解析成 `::1` → 打到的是那个 Java 服务（HTTP 500），`127.0.0.1` 才是 Flink（HTTP 200）。
处置：① Flink 宿主端口固定 **18088**（180xx 避让口径）；② 访问本机服务**一律用 `127.0.0.1`，不要用 `localhost`**。

```bash
curl -s http://127.0.0.1:18088/overview | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['taskmanagers'],d['slots-total'])"
# 期望: 1 3
```

**Q20：检查点配置写在 compose 的 JM/TM 上，作业却一次检查点都不做**
**作业级配置（检查点/重启策略）的唯一生效来源是提交端**：JobGraph 由 SQL Client 组装，不会把远端集群的作业级配置注入；集群侧那份只是"集群默认值"（供 `flink run` 等用）。
判据（端到端，不看配置）：

```bash
JID=$(curl -s http://127.0.0.1:18088/jobs/overview | python3 -c "import json,sys;print([j['jid'] for j in json.load(sys.stdin)['jobs'] if j['name']=='ov-online-count-1m'][0])")
curl -s "http://127.0.0.1:18088/jobs/${JID}/checkpoints" | python3 -c "import json,sys;print(json.load(sys.stdin)['counts'])"
# 期望 completed 随时间递增；恒为 0 = 配置没进 JobGraph
```

处置：提交端补齐（`lakehouse/warehouse/streaming/submit-jobs.sh` 的 `CLIENT_FLINK_PROPERTIES`）；两处同名键由 `scripts/check-docs.sh` ⑩ 逐键比对（值漂移即 CI 红）。

**Q21：作业提交后立刻 FAILED，日志 `Unexpected error in InitProducerIdResponse; The transaction timeout is larger than the maximum value allowed by the broker`**
Flink 的 Kafka sink 在 `exactly-once` 下 `transaction.timeout.ms` **默认 1 小时**（`KafkaSinkBuilder.DEFAULT_KAFKA_TRANSACTION_TIMEOUT`，javap 反汇编确认），broker 的 `transaction.max.timeout.ms` 默认 **15 分钟** → `InitProducerId` 被拒。
处置（本仓取前者——不动 broker）：
1. sink 显式 `'properties.transaction.timeout.ms' = '600000'`（10 分钟 > 检查点超时 5 分钟且 < broker 上限）。没有 `sink.transaction-timeout` 这个键（键名清单由 jar 内 `KafkaConnectorOptions` 反查）；`properties.*` 在默认值之后 `putAll`，用户值生效。
2. 或调大 broker 的 `transaction.max.timeout.ms`（代价是事务可挂更久）。

**Q22：检查点配好了却永远传不上去 —— TM 缺 `s3.*`**
真正把状态写到 `s3://` 的是 **TaskManager**；TM 缺 `s3.*` 时会按 Flink 默认端点（AWS 真 S3、无凭据）解析。现已两侧给全，门禁 ⑩ 单独钉 TM 侧四个键（删掉即红）。
（证据强度：这是配置语义推出的必然结果，本环境未实测到该故障表现——当时检查点根本没跑起来，见 Q20。）

**Q23：`FLINK_PROPERTIES` 里写注释，结果注释变成了配置项**
官方入口（`docker-entrypoint.sh` → `prepare_configuration`）把这串多行变量当 YAML 解析后写回 `conf/config.yaml`，**注释行同样参与解析**（实测 12 条注释全变怪键，行内空格被吞）。
处置：块内**只写 `key: value`**，说明写块外；`check-docs.sh` ⑩ 拒绝块内注释行。判据：

```bash
docker exec ov-flink-jm sh -c "grep -c \"^'#\" /opt/flink/conf/config.yaml"   # 期望: 0
```

**Q24：`sql-client` 报 `Failed to initialize from sql script: .../00-common.sql`，但 SQL 本身没问题**
两个独立原因：① conf 被只读挂载，而入口的 `prepare_configuration` 需要**写回**它（报 `Read-only file system`，表现为 SQL 初始化失败）——现在一律 `-e FLINK_PROPERTIES=...`，不挂 conf 文件；② `WITH (...)` 选项列表**不接受尾逗号**（`ParseException: Encountered ")" at line N`）。
定位：手动跑一次客户端并把输出留下来（别只看 `submit-jobs.sh` 的汇总行）：

```bash
docker run --rm --network oceanverse_ov-net --memory=640m \
  -e "FLINK_PROPERTIES=$(sed -n '/^CLIENT_FLINK_PROPERTIES="/,/\"$/p' lakehouse/warehouse/streaming/submit-jobs.sh | sed '1s/^CLIENT_FLINK_PROPERTIES="//; $s/\"$//')" \
  -v "$PWD/.tmp-realtime-submit:/opt/flink/sql:ro" oceanverse/flink:1.20.5 \
  /opt/flink/bin/sql-client.sh -f /opt/flink/sql/00-common.sql
```

**Q25：告警为"已经不存在的作业"持续 firing（Prometheus 残留 series 假阳性）**
`increase(<counter>[15m]) == 0` 对两类情况**同样成立**：① 作业在跑但零完成（要报）；② 作业已取消、series 还留着 15m 窗口内的样本（不该报——Flink 的 JM 指标在作业取消后仍会被暴露一段时间）。
修法：加"仍被暴露"守卫，只让当前仍被抓取的 series 参与判断：

```promql
increase(flink_jobmanager_job_numberOfCompletedCheckpoints[15m]) == 0
  and on(job_id) flink_jobmanager_job_numberOfCompletedCheckpoints
```

正负场景已固化成 promtool 单测（5 个场景，CI 里跑）；promtool 对 `exp_annotations` 是逐字比对，所以这两条规则的注解收敛成了单行、排查步骤写在规则文件注释里。

```bash
docker exec ov-prometheus promtool test rules /etc/prometheus/rules/tests/flink-checkpoints.test.yml
# 期望: SUCCESS
```

---

## 7. 附录：修订记录

> 这里按时间记录"为什么变成现在这样"；正文（§1–§6）只写当前事实。被折叠的 Q&A 条目也在此留一行。

| 日期 | 改了什么 | 为什么 |
|---|---|---|
| 2026-09-16 | 初版：Kafka / ClickHouse / MinIO / Grafana 四组件 + 镜像加速器 + 端口避让 | 最小可用链路底座 |
| 2026-09-16 | MQTT 压测改到容器网内进行 | 宿主→VM→容器转发层并发 ≈185 连接/端口（Q9） |
| 2026-09-17 | +EMQX / +Prometheus；EMQX 明文宿主端口 1883→11883 | 接入车端 MQTT；本机 RabbitMQ MQTT 插件抢占 1883（Q10） |
| 2026-09-18 | Kafka 数据显式入卷（KAFKA_LOG_DIRS）；全服务 `restart: unless-stopped` + `mem_limit` + 日志轮转；宿主端口统一 `127.0.0.1` 回环绑定 | 此前 down+up 会丢全部 topic 与位移；引擎重启后链路静默下线；弱口令组件不能暴露给同网段（Q14/Q15） |
| 2026-09-18 | +MySQL / +Redis（只建库不建表） | 第 4 步 Java 微服务的底座 |
| 2026-09-18 | 八容器 `mem_limit` 合计 6.88 GiB 超 VM 实测量（6.2 GiB）→ 整体压回 + ClickHouse 进程内上限落 `limits.xml` 并挂进容器 | 上限之和超物理内存 = 整机 OOM 风险 |
| 2026-09-18 | Prometheus 告警规则从无到有 | VM 掉线导致链路停摆而监控无人知晓（Q16） |
| 2026-09-20 | MinIO 镜像改 `quay.io/minio/minio`（digest 与 Docker Hub 一致） | Docker Hub 已拒绝匿名拉取，CI 干净环境首跑才发现 |
| 2026-09-20 | Rancher VM 6→8 GB；按实测用量重分配（ClickHouse 1280m→2560m，合计 6656 MiB） | CH 进程内上限余量不足 → "活着但干不了活"（Q17） |
| 2026-09-20 | Flink 入栈：自建镜像 `oceanverse/flink:1.20.5`（补连接器 jar）、profile `realtime`、宿主端口 18088 | 第 3 步实时作业；官方镜像不含连接器；8081 被公司 Java 服务占（Q18） |
| 2026-09-20 | Flink 告警 5 条补齐（规则总数 15）+ promtool 规则语义单测进 CI | 实时层此前零指标零告警；检查点类规则曾出现残留 series 假阳性（Q25） |
| 2026-09-20 | Prometheus 规则热载纪律：`--web.enable-lifecycle` + 改后必须 `/-/reload` | 规则文件是 bind mount，改完不 reload 则新规则不生效 |
| 2026-09-20 | P1 配置：检查点落 MinIO（镜像自带 s3 插件）、位点 `group-offsets`、sink exactly-once、作业级配置改到提交端（`CLIENT_FLINK_PROPERTIES`）、TM 补 `s3.*`、`FLINK_PROPERTIES` 只许 `key: value` | 检查点/位点/幂等落地过程中连踩四个静默配置坑（Q20–Q24） |
| 2026-09-20 | 折叠原 Q4（grafana 镜像固定 `latest`、不钉小版本号）与原 Q19（Flink 必须显式 `command: jobmanager/taskmanager`） | 修复已入库且回归有判据：镜像 tag 不存在会让 CI 镜像拉取直接红；compose 作业断言 `taskmanagers=1 & slots=3`。**Q 编号不回收**，历史文档中的 Q4/Q19 引用指向本行 |
| 2026-09-20 | 本文档结构整理：正文=当前事实，历史叙事收进本附录 | 补丁式留痕多轮后阅读成本过高 |
| 2026-09-20 | 修 §5 ⑨ Flink 块**丢失开围栏**的渲染错位（`# ⑨` 被渲染成 H1、后半篇代码/正文反转）；全仓 39 处无标签围栏补 ` ```text `；`check-docs.sh` 新增 ⑪ 围栏健康门禁 | 这类错位不报错、不挂 CI、只在渲染层崩——属"必须机械化"的一类（由渲染页人工发现） |
| 2026-09-20 | §3/§6 瘦身：解释与现场叙事全部删除（§3 字符 -18%、全文 559→467 行），Q&A 每条只留"现象→根因一句话→判据→处置" | 文档约定：**解释只写一遍**（在本附录或 Q&A 的根因行），不复述 |
