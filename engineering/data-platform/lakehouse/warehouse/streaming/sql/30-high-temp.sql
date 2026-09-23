SET 'pipeline.name' = 'mosaic-high-temp-battery-1m';
-- 并行度 1: 集群只有 3 个 slot, 而这是第 3 个作业 —— 三个作业各占 1 个正好用满。
--   横向扩: 加 TaskManager + 把这里改成 3（Kafka raw topic 已是 3 分区, 可直接吃满）。
SET 'parallelism.default' = '1';

-- 作业③: 高温电池（每车窗口内最高电池温度 ≥45℃）
--
-- 口径: 1 分钟窗口内**每辆车**的 `data.temp_max` 最大值, 超过阈值则出一条记录。
--   阈值(2026-09-20 定, 待固件/电池团队确认后进第 2 阶段口径字典):
--     warn  ≥ 45℃   —— 预警: 持续高温会加速衰减
--     alarm ≥ 55℃   —— 告警: 接近热失控风险区, 应对接告警服务
--   为什么按"窗口内最高温"而不是逐条上报: 车端 10s 一条, 逐条会把同一段高温刷成多条记录;
--   取窗口内峰值 = "这段时间这车有多热", 正好对上告警语义。
--
-- 数据来源: `type=battery_status`（二进制通道的 0x08/0x09 信息体解码后也是这个类型）。
-- 探针剔除同作业①。
INSERT INTO ads_high_temp_battery_1m
SELECT
    UNIX_TIMESTAMP(CAST(window_start AS STRING)) AS window_start_s,
    UNIX_TIMESTAMP(CAST(window_end AS STRING))   AS window_end_s,
    vin,
    temp_max,
    CASE WHEN temp_max >= 55 THEN 'alarm' ELSE 'warn' END AS `level`
FROM (
    SELECT
        window_start,
        window_end,
        vin,
        MAX(data.temp_max) AS temp_max
    FROM TABLE(TUMBLE(TABLE vehicle_report_raw, DESCRIPTOR(event_time), INTERVAL '1' MINUTE))
    WHERE `type` = 'battery_status'
      AND vin IS NOT NULL
      AND vin NOT LIKE 'OVPROBE%'
      AND data.temp_max IS NOT NULL
    GROUP BY window_start, window_end, vin
)
WHERE temp_max >= 45;
