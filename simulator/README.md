# Simulator - 车辆数据模拟器

## 功能

- 模拟 10,000 辆智能电动车
- 每 10 秒上报一次状态数据
- 注入 0.5% 异常数据（故障码、电池高温）
- HTTP POST 上报到接入网关

## 数据 Schema

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

## 运行

```bash
python simulator.py --vehicles 10000 --interval 10 --gateway http://localhost:8080/api/v1/report
```
