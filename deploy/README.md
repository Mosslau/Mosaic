# OceanVerse 期① 基础设施部署文档

> 适用阶段：第 1 阶段第 1 步——最小可用链路的底座
> 容器运行时：**Rancher Desktop**（moby 引擎，非 Docker Desktop，符合本机策略）
> 一键启动后你将得到：Kafka + ClickHouse + MinIO + Grafana 四个组件

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
| Kafka 3.9.1 (KRaft) | 消息总线 | `localhost:19092`（宿主机）/ 容器网内 `kafka:9092` | 无认证（期①本地） |
| ClickHouse 25.8 | OLAP serving 层 | HTTP `http://localhost:8123` / native `localhost:9000` | `ov_admin` / `ov_pass_2026` |
| MinIO | 对象存储（期②湖仓底座） | S3 API `http://localhost:9001` / 控制台 `http://localhost:9002` | `ov_minio` / `ov_minio_2026` |
| EMQX 5.8 | MQTT Broker（车端长连接接入） | MQTT `localhost:1883` / Dashboard `http://localhost:18083` | `admin` / `public`（**登录后立即改密**，或启动前设 `EMQX_DASHBOARD_PASSWORD` 环境变量） |
| Grafana OSS | 看板 | `http://localhost:3000` | `admin` / `admin` |

默认数据库：ClickHouse 自动建 `oceanverse` 库。
Grafana 启动后**自动配好名为 `ClickHouse` 的数据源**（provisioning，见 `deploy/grafana/provisioning/datasources/clickhouse.yaml`）。
EMQX 启动后**自动加载声明式规则**（`deploy/emqx/emqx.conf`）：把 `ov/+/status|battery|fault` 的消息经 Webhook 转发到 Go 网关（Dashboard → 集成 → 规则 可见 `ov_vehicle_ingress`）。

> 端口避让说明：MinIO 的 S3 API 映射到宿主 `9001`、控制台映射到 `9002`，因为 ClickHouse native 协议已占用 `9000`。

---

## 4. 启动 / 停止 / 重置

```bash
cd deploy

# 启动（首次会拉取镜像，约 1.5GB，视网络 5~20 分钟）
docker compose up -d

# 查看状态（healthy 即就绪）
docker compose ps

# 看日志（排查用）
docker compose logs -f kafka
docker compose logs -f clickhouse
docker compose logs -f minio
docker compose logs -f grafana

# 停止（数据保留在 volume 里）
docker compose down

# 完全重置（⚠️ 删除所有数据）
docker compose down -v
```

---

## 5. 启动后验证（四个组件逐一确认）

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
# 左侧 Connections → Data sources → 应看到已配好的 "ClickHouse"

# ⑤ EMQX：状态 + Dashboard
curl -s http://localhost:18083/status    # 期望: ok
open http://localhost:18083              # admin / public 登录(建议立即改密)
# Dashboard → 集成 → 规则: 应看到 ov_vehicle_ingress 规则 + webhook:device_gateway 动作
```

全部通过后，期①底座就绪，下一步是 Go 网关骨架（往 Kafka 写第一条车端数据）。

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
最常见是 EMQX 容器访问不到宿主机网关。依次试：① 确认网关已在本机 8080 启动；② 进入容器测试 `docker exec ov-emqx wget -qO- http://host.docker.internal:8080/health`；不通则把 `emqx.conf` 里 webhook url 的 `host.docker.internal` 换成 `host.lima.internal` 或宿主机局域网 IP，然后 `docker compose restart emqx`。
