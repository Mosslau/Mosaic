# OceanVerse 第 1 阶段 基础设施部署文档

> 📚 **简称约定**：《接入层设计》= 《../ingest/docs/01-接入层设计-v1.md》｜《GB32960 映射》= 《../ingest/docs/02-GB32960协议规格-v1.md》。

> 适用阶段：第 1 阶段第 1 步——最小可用链路的底座
> 容器运行时：**Rancher Desktop**（moby 引擎，非 Docker Desktop，符合本机策略）
> 一键启动后你将得到：Kafka + ClickHouse + MinIO + EMQX + Grafana + Prometheus 六个组件
> （原计划四组件，实际多 EMQX/Prometheus；`roadmap/项目进度.md` 记录为"另含 EMQX/Prometheus"）

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
| MinIO | 对象存储（第 2 阶段湖仓底座） | S3 API `http://localhost:9001` / 控制台 `http://localhost:9002` | `ov_minio` / `ov_minio_2026` |
| EMQX 5.8 | MQTT Broker（车端长连接接入；dev 明文 + 公网 TLS） | MQTT `localhost:1883`（**本机实测 1883 被 RabbitMQ MQTT 插件占用 → `.env` 已设 `EMQX_MQTT_PORT=11883`，即当前生效端口是 11883**；克隆后无 `.env` 则为 1883，模板见 `.env.example`）/ **TLS `localhost:8883`（一车一密 + ACL，见 Q12）** / Dashboard `http://localhost:18083` | `admin` / `public`（**登录后立即改密**，或启动前设 `EMQX_DASHBOARD_PASSWORD` 环境变量） |
| Grafana OSS | 看板 | `http://localhost:3000` | `admin` / `admin` |
| Prometheus | 指标采集（网关 `/metrics`，5s 抓取） | `http://localhost:9090` | 无认证（第 1 阶段本地） |

默认数据库：ClickHouse 自动建 `oceanverse` 库。
Grafana 启动后**自动配好名为 `ClickHouse` 的数据源**（provisioning，见 `deploy/grafana/provisioning/datasources/clickhouse.yaml`）。
EMQX 启动后**自动加载声明式规则**（`deploy/emqx/emqx.conf`）：① `ov_vehicle_ingress` —— `ov/+/status|battery|fault` → Webhook → 网关 `/api/v1/mqtt/ingest`；② `ov_binary_ingress` —— `ov/+/bin`（GB/T 32960 二进制帧，base64）→ 网关 `/api/v1/bin/ingest` → `ov.raw.binary.v1` → device-codec（Dashboard → 集成 → 规则 可见两条）。

> 端口避让说明：MinIO 的 S3 API 映射到宿主 `9001`、控制台映射到 `9002`，因为 ClickHouse native 协议已占用 `9000`。

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

# 查看状态（healthy 即就绪）
docker compose ps

# 看日志（排查用）
docker compose logs -f kafka
docker compose logs -f clickhouse
docker compose logs -f minio
docker compose logs -f grafana

# 停止（数据保留在 volume 里；Kafka 亦已显式 KAFKA_LOG_DIRS=/var/lib/kafka/data，
#  2026-09-18 前该卷是死配置、数据落在容器可写层，down+up 会丢全部 topic 与位移）
docker compose down

# 完全重置（⚠️ 删除所有数据）
docker compose down -v
```

---

## 5. 启动后验证（六个组件逐一确认）

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
# 左侧 Dashboards → 应看到两个面板:
#   "device-gateway 车端接入网关" (请求速率/延迟分位/受理vsKafka对账/在途)
#   "device-codec 编解码服务"     (消费vs解码/DLQ速率按stage/消费lag/微批耗时与批大小)

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
```

> **端口避让（本机实测）**：公司 Java 服务占用 8080~8083，网关开发期用 `GATEWAY_PORT=18080` 启动；
> `deploy/prometheus/prometheus.yml` 抓取目标与 `deploy/emqx/emqx.conf` webhook url 已对齐 18080（《接入层设计》§5.3 对齐线）。
> 若在 8080 空闲的机器上开发，两处改回 8080 即可。

全部通过后，第 1 阶段底座就绪，下一步是 Go 网关骨架（往 Kafka 写第一条车端数据）。

---

## 6. 常见问题（本次实测踩过的坑）

**Q1：`docker info` 连不上 daemon**
Rancher Desktop 没启动。`rdctl start`，等 1~4 分钟再试。

**Q2：拉镜像超时 `dial tcp ...:443: i/o timeout`**
镜像加速器未生效。检查第 2 节的 `override.yaml` 是否存在，然后 `rdctl shutdown && rdctl start` 重启，再 `rdctl shell cat /etc/docker/daemon.json` 确认 mirrors 在里面。

**Q3：拉镜像报 `403 Forbidden`（某镜像站抽风）**
直接重试 `docker compose pull`；仍不行则换镜像站单独拉再重打标签，例如：

```bash
docker pull docker.1ms.run/grafana/grafana-oss:latest
docker tag docker.1ms.run/grafana/grafana-oss:latest grafana/grafana-oss:latest
docker compose up -d
```

**Q4：`grafana/grafana-oss:12.2.0` 报 `not found`**
国内镜像站经常缺具体版本 tag。compose 里已固定用 `latest`，不要改回小版本号。

**Q5：拉取中途 `unexpected EOF`（网络抖动）**
重试即可，已下载的分层会续传：

```bash
for i in 1 2 3 4 5; do docker compose pull && break || sleep 5; done
```

**Q6：Grafana 数据源没有自动出现**
Grafana 首次启动需下载 ClickHouse 插件（`GF_INSTALL_PLUGINS`），网络慢时会等较久；看 `docker compose logs -f grafana`。插件装好后数据源才会生效，必要时 `docker compose restart grafana`。

**Q7：EMQX Dashboard 里看不到 `ov_vehicle_ingress` 规则**
规则由 `deploy/emqx/emqx.conf` 声明式定义。先确认挂载生效：`docker exec ov-emqx cat /opt/emqx/etc/emqx.conf | grep ov_vehicle_ingress`。若文件对但规则没生效，看 `docker compose logs emqx` 是否有配置解析错误（HOCON 字段名对版本敏感）；兜底方案：Dashboard → 集成 → 规则 → 手动新建（SQL 和 webhook 参数直接抄 `emqx.conf` 里对应段），5 分钟可完成。

**Q8：EMQX webhook 转发失败（规则监控里失败计数上涨）**
最常见是 EMQX 容器访问不到宿主机网关。依次试：① 确认网关已在本机 18080 启动；② 进入容器测试 `docker exec ov-emqx wget -qO- http://host.docker.internal:18080/health`；不通则把 `emqx.conf` 里 webhook url 的 `host.docker.internal` 换成 `host.lima.internal` 或宿主机局域网 IP，然后 `docker compose restart emqx`。

**Q9：宿主机跑 MQTT 模拟器，并发连接永远卡 ≈185、`connection reset by peer`**
Rancher Desktop 端口转发层（宿主→VM→容器）并发上限 ≈185 连接/端口（2026-09-16 实测：裸 socket 复现，网内直连 300/300 正常），EMQX 与网关无辜。**MQTT 压测改在容器网内跑**：

```bash
# 交叉编译 linux 二进制(静态, 任何镜像可承载)
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -o /tmp/msim-linux ./ingest/device-simulator/cmd/mqtt-simulator
cp /tmp/msim-linux .tmp-msim   # 放 workspace(Rancher 只共享 $HOME 给 VM, /tmp 挂不进)
docker run --rm --network oceanverse_ov-net -v $PWD/.tmp-msim:/msim:ro \
  --entrypoint /msim grafana/grafana-oss:latest \
  -broker tcp://emqx:1883 -devices 5000 -interval 5s -duration 60s
rm .tmp-msim
```

另注意：默认 6GB/2CPU 的 Rancher VM 跑 1 万 MQTT 长连接会**整机崩溃**（实测），本机 MQTT 档位上限按 5 千计；更大档位去专用压测节点。

**Q10：模拟器显示"连接成功/发布成功"，但 EMQX 里一个客户端/一条消息都没有**
宿主 1883 被别的 MQTT broker 抢了——模拟器连的是它，不是容器 EMQX（2026-09-17 实测：本机 RabbitMQ 装了 MQTT 插件，默认监听 1883；Rancher 端口映射后抢不过）。判据：`lsof -nP -iTCP:1883 -sTCP:LISTEN` 看到的不是容器转发进程；`docker exec ov-emqx emqx ctl clients list` 报 No clients。**处置（不动对方进程）**：compose 已参数化 `EMQX_MQTT_PORT`——写 `deploy/.env`（`EMQX_MQTT_PORT=11883`，已 gitignore）后 `docker compose up -d emqx` 永久生效，模拟器 `-broker tcp://localhost:11883`。同理，凡"连接正常但数据没到"先怀疑连错了 broker。

**Q11：codec/网关重启后消费组不消费（lag 不涨不落、新实例 consumed 恒 0）**
`pkill -f "go run ./cmd/server"` 只杀了 go run 包装进程，**编译产物子进程（exe/server）变孤儿还活着**，仍占着消费组成员位 → 新实例分不到分区。判据：`kafka-consumer-groups.sh --describe --group device-codec-v1 --members` 出现多个 member 且持分区者不是当前实例；`lsof -nP -iTCP:19092 -sTCP:ESTABLISHED` 数进程。**处置**：`pkill -f "exe/server"` 杀干净，等僵尸成员会话超时（~1 分钟，`--state` 变 Empty），再启动单个实例。
**附带坑**：codec 的可观测端点 `:18090` 也会被旧实例占住 —— 新实例日志会出现 `bind: address already in use`（主流程照跑，但 Prometheus 抓不到、面板空）；
重启前务必确认 `lsof -nP -iTCP:18090 -sTCP:LISTEN` 为空。生产 K8s 无此问题（容器即进程）；本地联调优先用 `go build` 出二进制再跑，杀起来干净。

**Q12：公网路径安全三件套（TLS / 一车一密 / ACL）怎么在本地跑起来**
三步（《接入层设计》§8.3）：

```bash
# ① 生成自签 CA + 服务器证书(仅本地! 生产换正式 CA)
bash deploy/emqx/gen-certs.sh
# ② 重建 EMQX 加载 8883 TLS 监听器 + 监听器级认证 + ACL
cd deploy && docker compose up -d emqx
# ③ 批量灌设备凭证(密码规则 pw-{VIN}, 仅 dev) 并自检六项
bash emqx/seed-users.sh 0 100
cd ../ingest/device-simulator && go run ./cmd/security-check -vin OV20260001
```

预期输出"六项全过"。生产形态连 8883：`go run ./cmd/bin-simulator -tls -broker localhost:8883 -cacert ../../deploy/emqx/certs/ca.crt`（clientid/username=VIN，无需改代码）。
**注意**：8883 对外开放前必须完成自检；本地自签证书与 `pw-` 密码规则**不得**用于生产。

**两个前提（2026-09-18 审计补充）**：

- **VIN 必须在已灌范围内**：`seed-users.sh` 默认灌 `OV00000000..OV00000099`；若自检用的 VIN 不在其中（如默认的 `OV20260001`），①④ 会以 `not Authorized` 失败。大号 VIN 用 `bash emqx/seed-users.sh --vin OV20260001` 单独灌。
- **容器重建后不必重新灌**：凭证存放在 mnesia 的 `data/mnesia/<节点名>/` 下。compose 已固定 `EMQX_NODE__NAME=emqx@127.0.0.1`（否则镜像 entrypoint 会按容器 IP 拼节点名，换 IP 即换空库 → 凭证静默失效，2026-09-18 实测 2/6 失败的根因）。重建后 `docker exec ov-emqx emqx eval 'node().'` 应仍为 `emqx@127.0.0.1`。

**Q14：为什么宿主端口从 `0.0.0.0` 改成了 `127.0.0.1`？**

第 1 阶段底座含弱口令（EMQX Dashboard `admin/public`、Grafana `admin/admin`）与无认证组件（Kafka、Prometheus）。
绑 `0.0.0.0` 时，笔记本接入公司网/公共网就等于把它们连同 ClickHouse 数据一起暴露给同网段，因此 compose 已统一改为
`127.0.0.1:PORT:PORT`。**容器间通信不受影响**（走 `ov-net`，用服务名 `kafka:9092`），README 里所有 `localhost:xxxx`
命令继续有效。若确需从局域网访问（如手机连 MQTT），临时加一条端口映射即可，别改回全网卡。

**Q15：容器为什么不自己恢复？**

2026-09-18 前 compose 里**没有任何 `restart:` 策略**，引擎/宿主重启后六容器保持 `Exited(137)`，链路静默下线且无告警。
现已统一 `restart: unless-stopped` + `mem_limit` + 日志轮转（`10m×3`）。验证方式：

```bash
rdctl shutdown && rdctl start --container-engine.name moby   # 模拟宿主重启
docker compose ps      # 无需任何 up 命令, 期望 6/6 healthy(实测通过)
```

> 注：`docker kill ov-kafka` 属于**显式停止**，`unless-stopped` 语义下不会自动拉起（这是预期行为）；验证自愈要用引擎重启。

**Q13：容器里的服务(网关/codec)写 Kafka 失败，但宿主机跑就正常**
Kafka 用了双监听器：`PLAINTEXT://kafka:9092`（容器网内）与 `EXTERNAL://localhost:19092`（宿主机）。
`EXTERNAL` 对外广播的地址是 `localhost:19092`——**在容器里 `localhost` 指向容器自身**，于是连不上（症状：网关 202 受理、
但 `gateway_kafka_write_total{result="error"}` 上涨、topic offset 不增）。处置：容器一律

```bash
docker run --network oceanverse_ov-net -e KAFKA_BROKERS=kafka:9092 ...
```

对照表：宿主机进程 → `localhost:19092`；容器内进程 → `kafka:9092`（且必须挂 `oceanverse_ov-net`）。
