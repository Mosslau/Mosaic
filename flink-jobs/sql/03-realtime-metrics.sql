-- 03: 实时指标计算

-- 实时在线车辆数 (5分钟内有上报)
CREATE VIEW realtime_online_vehicles AS
SELECT
    vehicle_id,
    MAX(event_time) as last_seen,
    COUNT(*) as event_count
FROM vehicle_events
GROUP BY vehicle_id
HAVING MAX(event_time) > CURRENT_TIMESTAMP - INTERVAL '5' MINUTE;

-- 实时故障车辆数
CREATE VIEW realtime_fault_vehicles AS
SELECT
    vehicle_id,
    fault_code,
    MAX(event_time) as last_fault_time
FROM vehicle_events
WHERE fault_code IS NOT NULL
GROUP BY vehicle_id, fault_code;

-- 实时高温电池告警
CREATE VIEW realtime_high_temp_alerts AS
SELECT
    vehicle_id,
    battery.temp as battery_temp,
    event_time
FROM vehicle_events
WHERE battery.temp > 55;

-- 写入 ClickHouse
INSERT INTO clickhouse_vehicle_events
SELECT
    vehicle_id,
    event_time,
    event_type,
    gps.lat,
    gps.lng,
    gps.speed,
    battery.voltage,
    battery.current,
    battery.temp,
    battery.soc,
    battery.soh,
    fault_code
FROM vehicle_events;
