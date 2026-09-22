-- OceanVerse Flink 实时作业 —— 共享表定义（用 sql-client 的 `-i` 载入, 三个作业公用）
--
-- 为什么把"源表 + 三个 sink"都放这里: 连接参数与字段映射是**单一源** ——
--   三个作业文件只写 INSERT, 避免 Kafka 地址 / ClickHouse 凭据 / 字段类型在三处各抄一份而漂移
--   （与本仓"topic 表只放设计文档 §4.2"是同一条纪律）。
--
-- 数据形状 = 接入层契约 `VehicleReport`（`ingest/device-contracts/vehicle/vehicle.go`）:
--   三条通道（HTTP / MQTT-JSON / 二进制 codec 产物）都在 `vehicle-report-raw` 汇聚 —— 下游只认这一份信封。
--
-- 关键取舍:
--   ① **保留字必须反引号**: `type`(类型) 与 `model`(CREATE MODEL) 都是保留字 ——
--      实测漏掉 `model` 的反引号时, 报错是 `Encountered "model" at line 32`(指向 DDL 而非作业, 容易看错地方)。
--   ② `data` 声明为 ROW, 只列作业用得到的字段; JSON format 对多余字段**默认忽略**,
--      故契约将来加字段不需要改这里。
--   ③ 时间语义: 契约 `ts` 是 Unix **秒**(GB32960 也是秒级) → `TO_TIMESTAMP_LTZ(ts, 0)`;
--      watermark 容忍 10s 乱序/迟到(车端弱网重传)。
--   ④ `json.ignore-parse-errors` 打开: 单条脏数据不能把整个作业打挂 —— 与接入层 DLQ 同一哲学
--      (失败隔离, 而不是让整条流停摆)。
--   ⑤ 启动位点 `group-offsets`(2026-09-20 起, 随检查点一起开): 有检查点 → **从检查点位移续跑**
--      (重启不再丢窗口); 首次启动无检查点 → 回落 `properties.auto.offset.reset=latest`。
--      同时因为开始提交位移, **Kafka 侧终于能看到 lag**（此前是监控盲点）。
--      **曾试 `earliest-offset` 做「重放式恢复」并实测否决**: 重启后从最早位点重放, 但追不上实时 ——
--      实测 5 分钟只推进 2 分钟事件时间, 指标迟迟不更新(机制见下 ⑤b)。
--   ⑤b `scan.watermark.idle-timeout = 30s`(2026-09-20 补): 某个分区 30s 没有数据就按「无水」处理,
--      水位线继续前进 —— 否则**一个安静的分区能把所有窗口都卡住**(3 个分区里只要 1 个没数据,
--      默认行为下整条水位线停住、窗口不触发)。
--   ⑤b **每个作业必须有独立的消费组**: 三个作业共用 `group.id` 时, Kafka 会把 3 个分区
--      **分给三个消费者各一个** —— 每个指标只能看到 **1/3 的数据**, 而且不会报错;
--      更早暴露的症状是反复 rebalance 导致源算子长时间一条不读(2026-09-20 实测)。
--      故 group.id 写成占位符 `__JOB_GROUP_ID__`, 由 `submit-jobs.sh` 按作业替换成
--      `flink-realtime-<作业>` 后再提交(Flink 的 SQL Client **不支持** ${VAR} 变量替换 —— 已实测)。
--   ⑥ sink 表名与 ClickHouse 目标表**同名**（`ads_*`）: 它就是这个表的写入端,
--      同名让 README/本文件/init.sql 三处可以对账（scripts/check-docs.sh 检查⑨ 会核对）。
--      sink 走 **Kafka 结果 topic**（不是 Flink 直连 ClickHouse）: Flink 侧没有可用的 ClickHouse
--      SQL 连接器（JDBC 工厂列表里没有 ClickHouse; 官方连接器只有 DataStream sink, 无 SQL 工厂 ——
--      详见 lakehouse/warehouse/streaming/clickhouse/init.sql 头注与 README）。落库由 ClickHouse 的 Kafka 引擎 + 物化视图完成。
--   ⑦ 时间戳一律以 **epoch 秒 (BIGINT)** 过 Kafka: 时间戳类型的 JSON 表示形式随格式/版本变化,
--      显式转整数可把"时区/格式"这类歧义挡在链路之外（ClickHouse 侧 toDateTime(秒) 直接还原）。
--      用秒而非毫秒: 窗口按分钟对齐, 秒精度**无损**; 且 Flink 不允许 CAST(TIMESTAMP AS BIGINT),
--      官方推荐写法是 UNIX_TIMESTAMP(CAST(ts AS STRING))（实测报错信息里给的就是这条）。
--   ⑧ **容器内**连 Kafka 用 `kafka:9092`(内部监听器), 不是宿主机那套 `localhost:19092`(deploy/README Q13)。
--
-- 指标口径的唯一源在 `lakehouse/warehouse/streaming/README.md` 的"指标口径"表; ClickHouse 三张表的 DDL 在
-- `lakehouse/warehouse/streaming/clickhouse/init.sql` —— 改字段/口径必须三处同步(README 表 / 本文件 sink / init.sql)。

-- ---------- 源表: Kafka raw topic ----------
CREATE TABLE IF NOT EXISTS vehicle_report_raw
(
    vin            STRING,
    ts             BIGINT,
    `type`         STRING,
    schema_version STRING,
    `model`        STRING,   -- model 同为保留字(CREATE MODEL), 必须反引号 —— 实测踩到
    data           ROW<
                       speed       DOUBLE,
                       soc         DOUBLE,
                       temp_max    DOUBLE,
                       temp_min    DOUBLE,
                       fault_codes ARRAY<STRING>
                   >,
    event_time AS TO_TIMESTAMP_LTZ(ts, 0),
    WATERMARK FOR event_time AS event_time - INTERVAL '10' SECOND
) WITH (
    'connector'                     = 'kafka',
    'topic'                         = 'vehicle-report-raw',
    'properties.bootstrap.servers'  = 'kafka:9092',
    'properties.group.id'           = '__JOB_GROUP_ID__',   -- 占位符: submit-jobs.sh 按作业替换(见下)
    -- 位点: 有检查点时**从检查点的位移续跑**(不丢窗口); 首次启动无检查点则回落 auto.offset.reset=latest
    'scan.startup.mode'             = 'group-offsets',
    'properties.auto.offset.reset'  = 'latest',
    'scan.watermark.idle-timeout'   = '30s',   -- 分区空闲 30s 即按「无水」推进水位线（见下 ⑤b）
    'scan.topic-partition-discovery.interval' = '30s',
    'format'                        = 'json',
    'json.ignore-parse-errors'      = 'true'
);

-- ---------- Sink ①: 在线数（1 分钟窗口去重车辆数）----------
CREATE TABLE IF NOT EXISTS ads_vehicle_online_1m
(
    window_start_s BIGINT,
    window_end_s   BIGINT,
    online_cnt      BIGINT,
    report_cnt      BIGINT
) WITH (
    'connector'                    = 'kafka',
    'topic'                        = 'ov.ads.vehicle_online_1m.v1',
    'properties.bootstrap.servers' = 'kafka:9092',
    'format'                       = 'json',
    'sink.delivery-guarantee'      = 'exactly-once',   -- 事务写: 结果 topic 里不出现"重试产生的重复"
    'sink.transactional-id-prefix' = '__JOB_TXN_PREFIX__',  -- 占位符: 每作业必须唯一(见 submit-jobs.sh)
    -- Flink Kafka sink 的 transaction.timeout.ms **默认 1 小时**(KafkaSinkBuilder 里
    -- DEFAULT_KAFKA_TRANSACTION_TIMEOUT=Duration.ofHours(1), 已用 javap 反汇编确认),
    -- 而 broker 的 transaction.max.timeout.ms 默认 15 分钟 → InitProducerId 直接失败:
    -- "The transaction timeout is larger than the maximum value allowed by the broker"(实测踩到)。
    -- 10 分钟 > 本作业 checkpoint timeout(5 分钟) + 余量, 且 < broker 上限, 故两侧都不用改。
    'properties.transaction.timeout.ms' = '600000'
);

-- ---------- Sink ②: 故障数（按 fault_code, 已按 (vin, ts, code) 去重）----------
CREATE TABLE IF NOT EXISTS ads_fault_count_1m
(
    window_start_s BIGINT,
    window_end_s   BIGINT,
    code            STRING,
    fault_cnt       BIGINT,
    vehicle_cnt     BIGINT
) WITH (
    'connector'                    = 'kafka',
    'topic'                        = 'ov.ads.fault_count_1m.v1',
    'properties.bootstrap.servers' = 'kafka:9092',
    'format'                       = 'json',
    'sink.delivery-guarantee'      = 'exactly-once',   -- 事务写: 结果 topic 里不出现"重试产生的重复"
    'sink.transactional-id-prefix' = '__JOB_TXN_PREFIX__',  -- 占位符: 每作业必须唯一(见 submit-jobs.sh)
    -- Flink Kafka sink 的 transaction.timeout.ms **默认 1 小时**(KafkaSinkBuilder 里
    -- DEFAULT_KAFKA_TRANSACTION_TIMEOUT=Duration.ofHours(1), 已用 javap 反汇编确认),
    -- 而 broker 的 transaction.max.timeout.ms 默认 15 分钟 → InitProducerId 直接失败:
    -- "The transaction timeout is larger than the maximum value allowed by the broker"(实测踩到)。
    -- 10 分钟 > 本作业 checkpoint timeout(5 分钟) + 余量, 且 < broker 上限, 故两侧都不用改。
    'properties.transaction.timeout.ms' = '600000'
);

-- ---------- Sink ③: 高温电池（每车窗口内最高温 ≥45℃）----------
CREATE TABLE IF NOT EXISTS ads_high_temp_battery_1m
(
    window_start_s BIGINT,
    window_end_s   BIGINT,
    vin             STRING,
    temp_max        DOUBLE,
    `level`         STRING
) WITH (
    'connector'                    = 'kafka',
    'topic'                        = 'ov.ads.high_temp_battery_1m.v1',
    'properties.bootstrap.servers' = 'kafka:9092',
    'format'                       = 'json',
    'sink.delivery-guarantee'      = 'exactly-once',   -- 事务写: 结果 topic 里不出现"重试产生的重复"
    'sink.transactional-id-prefix' = '__JOB_TXN_PREFIX__',  -- 占位符: 每作业必须唯一(见 submit-jobs.sh)
    -- Flink Kafka sink 的 transaction.timeout.ms **默认 1 小时**(KafkaSinkBuilder 里
    -- DEFAULT_KAFKA_TRANSACTION_TIMEOUT=Duration.ofHours(1), 已用 javap 反汇编确认),
    -- 而 broker 的 transaction.max.timeout.ms 默认 15 分钟 → InitProducerId 直接失败:
    -- "The transaction timeout is larger than the maximum value allowed by the broker"(实测踩到)。
    -- 10 分钟 > 本作业 checkpoint timeout(5 分钟) + 余量, 且 < broker 上限, 故两侧都不用改。
    'properties.transaction.timeout.ms' = '600000'
);
