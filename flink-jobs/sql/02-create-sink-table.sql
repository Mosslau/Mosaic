-- 02: 创建 ClickHouse Sink 表

CREATE TABLE clickhouse_vehicle_events (
    vehicle_id STRING,
    event_time TIMESTAMP(3),
    event_type STRING,
    lat DOUBLE,
    lng DOUBLE,
    speed FLOAT,
    battery_voltage FLOAT,
    battery_current FLOAT,
    battery_temp FLOAT,
    soc INT,
    soh INT,
    fault_code STRING,
    PRIMARY KEY (vehicle_id, event_time) NOT ENFORCED
) WITH (
    'connector' = 'clickhouse',
    'url' = 'clickhouse://clickhouse:8123',
    'database-name' = 'oceanverse',
    'table-name' = 'ods_vehicle_event',
    'username' = 'default',
    'password' = 'oceanverse123',
    'sink.batch-size' = '1000',
    'sink.flush-interval' = '1s',
    'sink.max-retries' = '3'
);
