SET 'pipeline.name' = 'mosaic-fault-count-1m';
-- 并行度 1: 集群只有 3 个 slot, 而这是第 3 个作业 —— 三个作业各占 1 个正好用满。
--   横向扩: 加 TaskManager + 把这里改成 3（Kafka raw topic 已是 3 分区, 可直接吃满）。
SET 'parallelism.default' = '1';

-- 作业②: 故障数（按 fault_code 分组, 1 分钟滚动窗口）
--
-- 口径: 1 分钟窗口内每个 fault_code 的**故障次数**与涉及车辆数。
--
-- 为什么必须先按 (vin, ts, code) 去重:
--   故障事件走 **QoS1**（《接入层设计》§4.2）, 同一条会被**重复投递**;
--   不去重就会把"一次故障"算成多次 —— 这是本作业唯一的正确性前提, 不是优化。
--   去重键取 (vin, ts, code): 同一辆车同一秒的同一种故障码只算一次; 不同秒/不同码各算一次。
--
-- 探针剔除同作业①。
INSERT INTO ads_fault_count_1m
SELECT
    UNIX_TIMESTAMP(CAST(window_start AS STRING)) AS window_start_s,
    UNIX_TIMESTAMP(CAST(window_end   AS STRING)) AS window_end_s,
    code,
    COUNT(*)                     AS fault_cnt,
    COUNT(DISTINCT vin)          AS vehicle_cnt
FROM (
    -- 先去重: 同一 (vin, ts, code) 只算一次（故障走 QoS1, 同一条会被重复投递）
    SELECT window_start, window_end, vin, ts, code
    FROM (
        -- 先把数组**投影成列**: 窗口 TVF 之后直接写 `data.fault_codes` 会报
        -- `Column 'data.data' not found`（实测踩到）—— 先投影再 UNNEST 才是稳的写法
        SELECT window_start, window_end, vin, ts, data.fault_codes AS fault_codes
        FROM TABLE(TUMBLE(TABLE vehicle_report_raw, DESCRIPTOR(event_time), INTERVAL '1' MINUTE))
        WHERE `type` = 'fault'
          AND vin IS NOT NULL
          AND vin NOT LIKE 'OVPROBE%'
          AND data.fault_codes IS NOT NULL
    ) AS w
    CROSS JOIN UNNEST(w.fault_codes) AS t(code)
    GROUP BY window_start, window_end, vin, ts, code
)
GROUP BY window_start, window_end, code;
