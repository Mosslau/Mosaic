-- OceanVerse ClickHouse 初始化脚本

CREATE DATABASE IF NOT EXISTS oceanverse;

-- ODS: 原始车辆事件表
CREATE TABLE IF NOT EXISTS oceanverse.ods_vehicle_event
(
    vehicle_id String,
    timestamp DateTime64(3),
    event_type LowCardinality(String),
    lat Float64,
    lng Float64,
    speed Float32,
    battery_voltage Float32,
    battery_current Float32,
    battery_temp Float32,
    soc UInt8,
    soh UInt8,
    fault_code Nullable(String),
    received_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (vehicle_id, timestamp)
TTL timestamp + INTERVAL 90 DAY;

-- DWD: 清洗后的车辆状态明细
CREATE TABLE IF NOT EXISTS oceanverse.dwd_vehicle_status
(
    vehicle_id String,
    event_time DateTime64(3),
    lat Float64,
    lng Float64,
    speed Float32,
    battery_voltage Float32,
    battery_current Float32,
    battery_temp Float32,
    soc UInt8,
    soh UInt8,
    is_anomaly Bool,
    anomaly_type Nullable(String)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(event_time)
ORDER BY (vehicle_id, event_time);

-- DWS: 车辆健康日汇总
CREATE TABLE IF NOT EXISTS oceanverse.dws_vehicle_health_day
(
    vehicle_id String,
    stat_date Date,
    total_events UInt32,
    fault_count UInt16,
    max_battery_temp Float32,
    min_soc UInt8,
    avg_speed Float32,
    total_mileage Float32,
    health_score UInt8
)
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(stat_date)
ORDER BY (vehicle_id, stat_date);

-- 实时在线车辆物化视图
CREATE MATERIALIZED VIEW IF NOT EXISTS oceanverse.mv_vehicle_online
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(stat_date)
ORDER BY (stat_date, vehicle_id)
POPULATE
AS SELECT
    toDate(timestamp) as stat_date,
    vehicle_id,
    maxState(timestamp) as last_seen
FROM oceanverse.ods_vehicle_event
GROUP BY stat_date, vehicle_id;
