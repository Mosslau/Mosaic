-- OceanVerse 实时作业结果表（第 1 阶段第 3 步）
--
-- 定位: ClickHouse 是 **serving 层**, 不是真相源(真相源是第 2 阶段的 Iceberg 湖仓)。
--       这三张表是 **ADS 层**产物 —— 由 Flink 作业算出、经 Kafka 结果 topic 灌入, 只服务查询/看板。
--
-- 为什么经 Kafka 而不是 Flink 直连 ClickHouse（2026-09-20 实测后的决策, 详见 realtime/README.md）:
--   Flink 侧**没有可用的 ClickHouse SQL 连接器** ——
--     · flink-connector-jdbc 3.4.0 的工厂列表里没有 ClickHouse(实测报错把 9 个工厂全列了出来);
--     · ClickHouse 官方 flink-connector-clickhouse 只有 DataStream 的 sink 类, **没有 Table/SQL 工厂**
--       (内省 0.2.0/0.1.3 的 jar: 只有 org/apache/flink/connector/clickhouse/sink/*, 无 Factory 类、无 SPI);
--     · Maven Central 上其余 "clickhouse flink" 构件都是 StreamX/StreamPark 等框架专用或早已不在 Central。
--   于是采用 ClickHouse 原生范式: **Kafka 引擎表(入口) + 物化视图(搬运) + MergeTree(落库)** ——
--   全 SQL、无协议 hack, 且结果留在 Kafka 里可回放。
--
-- 幂等语义（诚实记录）: Kafka 引擎是 **at-least-once**, CH 重启后可能重放少量消息 →
--   目标表用 **ReplacingMergeTree** + 与业务键一致的 ORDER BY 抗重复;
--   查询若要求"精确去重"请用 `FINAL` 或先 GROUP BY（第 1 阶段看板查询量小, 直接查即可）。
--
-- 指标口径（**唯一源**在 realtime/README.md 的"指标口径"表; 改一处必须改另两处: 本文件 / 00-common.sql）:
--   ads_vehicle_online_1m     1 分钟滚动窗口内"上报过的去重车辆数"（在线数的近似口径, 不是长连接在线）
--   ads_fault_count_1m        1 分钟窗口内按 fault_code 分组的故障次数, 已按 (vin, ts, code) 去重
--   ads_high_temp_battery_1m  1 分钟窗口内每车最高电池温度 ≥45℃; level: warn(≥45) / alarm(≥55)
--
-- 探针帧（`scripts/check-pipeline-health.sh` 灌的 OVPROBE* 帧）在 Flink SQL 里就被剔除, 到不了这里。
--
-- 应用方式(实测: ClickHouse 的 HTTP 口**不支持一次多条语句** —— "Multi-statements are not allowed",
--   故走容器内 client 的 --multiquery; 另外 curl 对 SQL 错误仍返回 0, 不能只看退出码):
--   docker exec -i ov-clickhouse clickhouse-client --user ov_admin --password ov_pass_2026 --multiquery < realtime/clickhouse/init.sql

-- ============================================================
-- ① 在线数
-- ============================================================
CREATE TABLE IF NOT EXISTS oceanverse.ads_vehicle_online_1m
(
    window_start DateTime('Asia/Shanghai'),
    window_end   DateTime('Asia/Shanghai'),
    online_cnt   UInt32,                     -- 去重车辆数
    report_cnt   UInt64,                     -- 窗口内上报条数(用于与 Kafka/网关对账)
    ingested_at  DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMMDD(window_start)
ORDER BY window_start                       -- 一个窗口一行 → 天然去重键
TTL window_start + INTERVAL 90 DAY;

CREATE TABLE IF NOT EXISTS oceanverse.kafka_vehicle_online_1m
(
    window_start_s Int64,
    window_end_s   Int64,
    online_cnt      UInt32,
    report_cnt      UInt64
)
ENGINE = Kafka
SETTINGS kafka_broker_list = 'kafka:9092',
         kafka_topic_list = 'ov.ads.vehicle_online_1m.v1',
         kafka_group_name = 'ch-ads-vehicle-online-1m-v1',
         kafka_format = 'JSONEachRow',
         kafka_num_consumers = 1,
         kafka_flush_interval_ms = 2000,
         kafka_skip_broken_messages = 100;

CREATE MATERIALIZED VIEW IF NOT EXISTS oceanverse.mv_vehicle_online_1m
TO oceanverse.ads_vehicle_online_1m
AS SELECT
    toDateTime(window_start_s) AS window_start,
    toDateTime(window_end_s) AS window_end,
    online_cnt,
    report_cnt,
    now() AS ingested_at
FROM oceanverse.kafka_vehicle_online_1m;

-- ============================================================
-- ② 故障数
-- ============================================================
CREATE TABLE IF NOT EXISTS oceanverse.ads_fault_count_1m
(
    window_start DateTime('Asia/Shanghai'),
    window_end   DateTime('Asia/Shanghai'),
    code         LowCardinality(String),     -- fault_code
    fault_cnt    UInt64,                     -- 去重后的故障次数
    vehicle_cnt  UInt32,                     -- 涉及的车辆数
    ingested_at  DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMMDD(window_start)
ORDER BY (window_start, code)
TTL window_start + INTERVAL 365 DAY;         -- 故障保留期更长(与位置类数据区分)

CREATE TABLE IF NOT EXISTS oceanverse.kafka_fault_count_1m
(
    window_start_s Int64,
    window_end_s   Int64,
    code            String,
    fault_cnt       UInt64,
    vehicle_cnt     UInt32
)
ENGINE = Kafka
SETTINGS kafka_broker_list = 'kafka:9092',
         kafka_topic_list = 'ov.ads.fault_count_1m.v1',
         kafka_group_name = 'ch-ads-fault-count-1m-v1',
         kafka_format = 'JSONEachRow',
         kafka_num_consumers = 1,
         kafka_flush_interval_ms = 2000,
         kafka_skip_broken_messages = 100;

CREATE MATERIALIZED VIEW IF NOT EXISTS oceanverse.mv_fault_count_1m
TO oceanverse.ads_fault_count_1m
AS SELECT
    toDateTime(window_start_s) AS window_start,
    toDateTime(window_end_s) AS window_end,
    code,
    fault_cnt,
    vehicle_cnt,
    now() AS ingested_at
FROM oceanverse.kafka_fault_count_1m;

-- ============================================================
-- ③ 高温电池
-- ============================================================
CREATE TABLE IF NOT EXISTS oceanverse.ads_high_temp_battery_1m
(
    window_start DateTime('Asia/Shanghai'),
    window_end   DateTime('Asia/Shanghai'),
    vin          LowCardinality(String),
    temp_max     Float32,                    -- 窗口内该车最高电池温度 ℃
    level        LowCardinality(String),     -- warn(≥45) / alarm(≥55)
    ingested_at  DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMMDD(window_start)
ORDER BY (window_start, vin)
TTL window_start + INTERVAL 180 DAY;

CREATE TABLE IF NOT EXISTS oceanverse.kafka_high_temp_battery_1m
(
    window_start_s Int64,
    window_end_s   Int64,
    vin             String,
    temp_max        Float32,
    level           String
)
ENGINE = Kafka
SETTINGS kafka_broker_list = 'kafka:9092',
         kafka_topic_list = 'ov.ads.high_temp_battery_1m.v1',
         kafka_group_name = 'ch-ads-high-temp-battery-1m-v1',
         kafka_format = 'JSONEachRow',
         kafka_num_consumers = 1,
         kafka_flush_interval_ms = 2000,
         kafka_skip_broken_messages = 100;

CREATE MATERIALIZED VIEW IF NOT EXISTS oceanverse.mv_high_temp_battery_1m
TO oceanverse.ads_high_temp_battery_1m
AS SELECT
    toDateTime(window_start_s) AS window_start,
    toDateTime(window_end_s) AS window_end,
    vin,
    temp_max,
    level,
    now() AS ingested_at
FROM oceanverse.kafka_high_temp_battery_1m;
