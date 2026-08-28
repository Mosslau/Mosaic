# Vehicle Service - 车辆档案服务

## 功能

- 车辆 CRUD
- Redis 缓存
- Kafka 消费车辆事件
- Prometheus 指标暴露

## 端口

8081

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/vehicles | 车辆列表 |
| GET | /api/v1/vehicles/{id} | 车辆详情 |
| POST | /api/v1/vehicles | 创建车辆 |
| PUT | /api/v1/vehicles/{id} | 更新车辆 |
| DELETE | /api/v1/vehicles/{id} | 删除车辆 |
| GET | /api/v1/vehicles/health | 健康检查 |

## 运行

```bash
mvn spring-boot:run
```
