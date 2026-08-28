-- 01: 创建 Kafka Source 表

CREATE TABLE vehicle_events (
    vehicle_id STRING,
    `timestamp` BIGINT,
    event_type STRING,
    gps ROW<
        lat DOUBLE,
        lng DOUBLE,
        speed FLOAT
    >,
    battery ROW<
        voltage FLOAT,
        current FLOAT,
        temp FLOAT,
        soc INT,
        soh INT
    >,
    fault_code STRING,
    event_time AS TO_TIMESTAMP_LTZ(`timestamp` * 1000, 3),
    WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'vehicle-events',
    'properties.bootstrap.servers' = 'kafka:9092',
    'properties.group.id' = 'flink-consumer',
    'scan.startup.mode' = 'earliest-offset',
    'format' = 'json',
    'json.ignore-parse-errors' = 'true'
);
