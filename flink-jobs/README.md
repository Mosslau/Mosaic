# Flink Jobs - 实时计算任务

## 功能

- 消费 Kafka 车辆事件
- Flink SQL 实时指标计算
- 写入 ClickHouse

## 目录结构

```
flink-jobs/
├── sql/
│   ├── 01-create-source-table.sql
│   ├── 02-create-sink-table.sql
│   └── 03-realtime-metrics.sql
└── pom.xml (如需 Java/Scala 扩展)
```

## 运行

通过 Flink SQL Client 或提交到 JobManager:

```bash
# 进入 Flink SQL Client
docker exec -it oceanverse-flink-jm ./bin/sql-client.sh

# 或提交 SQL 文件
docker exec -it oceanverse-flink-jm ./bin/sql-client.sh -f /path/to/sql/01-create-source-table.sql
```
