SET 'pipeline.name' = 'ov-online-count-1m';
-- 并行度 1: 集群只有 3 个 slot, 而这是第 3 个作业 —— 三个作业各占 1 个正好用满。
--   横向扩: 加 TaskManager + 把这里改成 3（Kafka raw topic 已是 3 分区, 可直接吃满）。
SET 'parallelism.default' = '1';

-- 作业①: 车辆在线数（1 分钟滚动窗口）
--
-- 口径: 窗口内**上报过的去重车辆数** —— 是"活跃车辆数"的近似, **不等于** MQTT 长连接在线数。
--   已知边界: 车端上报周期 10~30s, 1 分钟窗口能覆盖正常心跳; 心跳更稀疏的车会被算成离线。
--   （第 2 阶段口径字典扩到 7 个指标时, 会另加"最近 5 分钟有心跳即在线"的离线判定, 两者并存而非替换。）
--
-- 探针剔除: `OVPROBE*` 是 `scripts/check-pipeline-health.sh` 的探针保留段（第十轮约定）——
--   探针帧真实走完链路, 若不过滤会被当成真实车辆, 污染在线数/故障数/画像。
--
-- 提交方式见 lakehouse/warehouse/streaming/README.md（sql-client -i 00-common.sql -f 本文件）。
INSERT INTO ads_vehicle_online_1m
SELECT
    UNIX_TIMESTAMP(CAST(window_start AS STRING)) AS window_start_s,
    UNIX_TIMESTAMP(CAST(window_end AS STRING))   AS window_end_s,
    COUNT(DISTINCT vin)          AS online_cnt,
    COUNT(*)                     AS report_cnt
FROM TABLE(TUMBLE(TABLE vehicle_report_raw, DESCRIPTOR(event_time), INTERVAL '1' MINUTE))
WHERE vin IS NOT NULL
  AND vin NOT LIKE 'OVPROBE%'
GROUP BY window_start, window_end;
