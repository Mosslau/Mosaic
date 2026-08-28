# 🌊 OceanVerse

> **百川汇洋，数据纳乾坤**
>
> *From a thousand streams, one ocean.*

**A big data platform: Ingestion · Processing · Serving.**

智能电动车数据智能平台——从车端数据采集接入、实时流处理，到分析服务化输出与可视化监控，构建完整的数据水利工程。

## Why "OceanVerse"?

In Greek mythology, all rivers and springs eventually flow into Oceanus,
the great river encircling the world. Data follows the same journey —
from scattered streams into one ocean of insight.

## 架构概览

```
Simulator (车辆模拟器)
    │  HTTP POST
    ▼
Gateway (Go · 接入网关 :8080)
    │  Kafka (vehicle-events)
    ▼
Flink SQL (实时指标计算)
    │  Sink
    ▼
ClickHouse (实时数仓 :8123)
    │
    ├──▶ Analysis Service (Python FastAPI :8000)  健康评分 / 故障分析 / 电池风险
    └──▶ Grafana (监控看板 :3000)

Vehicle Service (Java Spring Boot :8081)  车辆档案 CRUD / Redis 缓存 / Kafka 消费
Prometheus (:9090)                        指标采集
```

## 模块速览

| 目录 | 技术栈 | 说明 |
|------|--------|------|
| `simulator/` | Python | 车辆数据模拟器：10,000 辆车、10s 上报周期、0.5% 异常注入 |
| `gateway/` | Go | 车端数据接入网关：HTTP 上报接收、Schema 校验、写入 Kafka |
| `flink-jobs/` | Flink SQL | 实时计算：Kafka → 指标计算 → ClickHouse |
| `services/vehicle-service/` | Java · Spring Boot | 车辆档案服务：CRUD、Redis 缓存、Kafka 消费、Prometheus 指标 |
| `services/analysis-service/` | Python · FastAPI | 数据分析服务：健康评分、故障汇总、电池风险、实时指标查询 |
| `deploy/` | Docker Compose | 基础设施：Kafka / Flink / ClickHouse / PostgreSQL / Redis / Grafana / Prometheus |
| `roadmap/` | Markdown | 架构设计与规划文档 |

## 快速开始

### 1. 启动基础设施

```bash
cd deploy
docker compose up -d
```

包含 Kafka、Flink（JM + 2×TM）、ClickHouse、PostgreSQL、Redis、Grafana、Prometheus。

### 2. 提交实时计算任务

```bash
docker exec -it oceanverse-flink-jm ./bin/sql-client.sh
# 依次执行 flink-jobs/sql/ 下的 01 → 02 → 03
```

### 3. 启动接入网关

```bash
cd gateway
go run main.go    # 监听 :8080
```

### 4. 启动业务服务

```bash
# 车辆档案服务 (:8081)
cd services/vehicle-service && mvn spring-boot:run

# 数据分析服务 (:8000)
cd services/analysis-service && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 灌入模拟数据

```bash
cd simulator
pip install -r requirements.txt
python simulator.py --vehicles 10000 --interval 10 \
  --gateway http://localhost:8080/api/v1/report
```

### 6. 查看效果

| 入口 | 地址 | 说明 |
|------|------|------|
| Grafana | http://localhost:3000 | 车辆监控看板（admin / oceanverse123） |
| Prometheus | http://localhost:9090 | 指标采集 |
| Flink Web UI | http://localhost:8081 | 作业管理 |
| Analysis API | http://localhost:8000/docs | Swagger 文档 |
| ClickHouse | http://localhost:8123 | HTTP 接口 |

## 数据 Schema

车端上报事件：

```json
{
  "vehicle_id": "V000001",
  "timestamp": 1724860800,
  "event_type": "status | fault | trip | battery",
  "gps": {"lat": 31.23, "lng": 121.47, "speed": 25.5},
  "battery": {"voltage": 60.2, "current": -5.1, "temp": 35.0, "soc": 78, "soh": 92},
  "fault_code": null
}
```

## License

MIT
