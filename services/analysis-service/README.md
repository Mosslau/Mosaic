# Analysis Service - 车辆数据分析服务

## 功能

- 车辆健康评分 API
- 故障码解释 API
- 电池风险计算 API
- 实时指标查询

## 端口

8000

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/health | 健康检查 |
| GET | /api/v1/metrics/online-vehicles | 在线车辆数 |
| GET | /api/v1/metrics/fault-summary | 故障汇总 |
| GET | /api/v1/metrics/battery-risk | 电池风险 |
| GET | /api/v1/metrics/vehicle-health/{id} | 车辆健康分 |

## 运行

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
