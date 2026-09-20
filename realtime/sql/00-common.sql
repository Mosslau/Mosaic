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
--   ⑤ 启动位点 `latest-offset`: 只消费新数据, 不重放历史(重启会丢半开的窗口 —— 第 1 阶段接受;
--      第 2 阶段用 checkpoint + 幂等落表收口)。
--   ⑥ sink 表名与 ClickHouse 目标表**同名**（`ads_*`）: 它就是这个表的写入端,
--      同名让 README/本文件/init.sql 三处可以对账（scripts/check-docs.sh 检查⑨ 会核对）。
--      sink 走 **Kafka 结果 topic**（不是 Flink 直连 ClickHouse）: Flink 侧没有可用的 ClickHouse
--      SQL 连接器（JDBC 工厂列表里没有 ClickHouse; 官方连接器只有 DataStream sink, 无 SQL 工厂 ——
--      详见 realtime/clickhouse/init.sql 头注与 README）。落库由 ClickHouse 的 Kafka 引擎 + 物化视图完成。
--   ⑦ 时间戳一律以 **epoch 秒 (BIGINT)** 过 Kafka: 时间戳类型的 JSON 表示形式随格式/版本变化,
--      显式转整数可把"时区/格式"这类歧义挡在链路之外（ClickHouse 侧 toDateTime(秒) 直接还原）。
--      用秒而非毫秒: 窗口按分钟对齐, 秒精度**无损**; 且 Flink 不允许 CAST(TIMESTAMP AS BIGINT),
--      官方推荐写法是 UNIX_TIMESTAMP(CAST(ts AS STRING))（实测报错信息里给的就是这条）。
--   ⑧ **容器内**连 Kafka 用 `kafka:9092`(内部监听器), 不是宿主机那套 `localhost:19092`(deploy/README Q13)。
--
-- 指标口径的唯一源在 `realtime/README.md` 的"指标口径"表; ClickHouse 三张表的 DDL 在
-- `realtime/clickhouse/init.sql` —— 改字段/口径必须三处同步(README 表 / 本文件 sink / init.sql)。

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
    'properties.group.id'           = 'flink-realtime-v1',
    'scan.startup.mode'             = 'latest-offset',
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
    'format'                       = 'json'
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
    'format'                       = 'json'
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
    'format'                       = 'json'
);
