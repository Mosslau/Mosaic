# Gateway - 车端数据接入网关

## 功能

- HTTP POST 接收车辆数据上报
- 设备鉴权（待扩展）
- 数据校验（Schema 验证）
- 写入 Kafka
- 健康检查

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `KAFKA_BROKERS` | `localhost:9092` | Kafka 地址 |
| `KAFKA_TOPIC` | `vehicle-events` | Kafka Topic |
| `PORT` | `8080` | 服务端口 |

## API

### POST /api/v1/report

上报车辆数据

```json
{
  "events": [...],
  "source": "simulator",
  "timestamp": 1724860800
}
```

### GET /api/v1/health

健康检查

## 运行

```bash
go run main.go
```
