# ph17 消息队列与搜索 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：OpenJDK 17 + Maven 3.9 + Spring Boot 3.3.0 + spring-kafka 3.2.0 / kafka-clients 3.7.0 / ES 8.x Java client（依赖坐标与 pom 见 examples/ex02、examples/ex05）。**本环境未验证任何题解**：纯 Java/JUnit 部分理论上离线可跑（命令 `mvn -o -Dmaven.repo.local=/tmp/m2clone test`），Kafka/ES 链路需先起 `docker compose`（examples/README.md）——全部如实标注「未在本环境验证」。

**与 roadmap「17. 消息队列与搜索阶段」练习小节的对应**：四题一一对应 roadmap 列的四个练习——练习 1 = 异步订单处理、练习 2 = 车辆数据消费、练习 3 = 告警消息推送、练习 4 = 日志搜索。四题合起来是「消息 + 搜索」的一条完整技能线：异步化与幂等（1）→ 分区顺序与状态聚合（2）→ 重试/延迟/死信（3）→ 索引设计与检索（4），做完即具备本阶段 project（设备事件搜索系统）的全部零件。

sol-* 为参考实现（文件头已注明验证环境、命令与「未在本环境验证」标注），做完再看。四题都是「源代码合集 + 注释里的 pom 来源」：按文件内注释把每个文件写入标准 Maven 工程后验证（pom 复制 examples/ex02 的——练习 4 复制 examples/ex05 的；跑 JUnit 测试需追加 test-scope 的 `spring-boot-starter-test`，版本由 Boot 3.3.0 父 POM 管理）。

## 练习 1：异步订单处理（★★）

**目标**：把「下单后的耗时动作」异步化——写一个消费 `orders` topic 的订单处理器，消费端做到 at-least-once 语义下的幂等建单，理解「重复不可避免、幂等必须设计在消费端」。
**要求**：

- 工程 = examples/ex02 的 pom，topic `orders`、group `async-order-group`，监听方法带 `Acknowledgment`（`ack-mode: manual`）
- 幂等双层：① 请求/消息级——TTL 去重表（自己实现，别抄 ex02 的类）；② 业务级——订单表按 `orderId` 唯一（内存 `putIfAbsent` 等价唯一索引，生产是数据库唯一约束）
- 消息处理失败（如 JSON 解析异常）也要有明确策略：记录并继续 ack（可重放的坏消息别让消费者卡死），或抛异常交给容器重试——两种策略都要能说出取舍
- 纯逻辑部分配 JUnit：同一 orderId 处理两次，建单计数只 +1

**验收**：参考实现实测 `Tests run: 3`（同 key 重复投递只建一次 / 不同 key 各自建 / 去重表 TTL 窗口过期后重放放行，业务唯一键兜底）；能说出「先处理再提交」为什么必然重复、为什么去重表挡不住「很晚的重复」。

## 练习 2：车辆数据消费（★★★）

**目标**：消费平台指标数据（roadmap 第 17 节练习 + 第 21 节铺垫），落实「分区影响顺序和吞吐」——按数据源 ID 分区，单源数据有序，每个数据源独立聚合。
**要求**：

- topic `vehicle.telemetry`，消息 key = 车辆 `sn`（同 sn 恒进同分区 → 单车顺序，主文档 3.5）；group `telemetry-aggregator`，手动 ack
- 消费端维护每车聚合：最近 5 条的平均车速、最高车速、最新电量——用 `ConcurrentHashMap<sn, Stats>` 持有状态（练习只做单实例内存聚合；分布式去重/状态外置是进阶，可注明）
- 幂等：`(sn, seq)` 去重（Kafka 至少一次 + 单车分区，重复与乱序同时防；迟到的旧 seq 丢弃）
- 超速检测：speed > 120 打一条聚合日志/计数（真实系统在此发告警事件 → 练习 3 的主题）
- 纯逻辑部分配 JUnit：乱序到达（旧 seq 后到）不破坏统计、重复投递不重复计入

**验收**：参考实现实测 `Tests run: 4`；能画出「同 sn 同分区 → 单车顺序 → 单车状态聚合」的链路，并说出消费者扩容为什么受分区数限制（roadmap 必会概念）。

## 练习 3：告警消息推送（★★★）

**目标**：把「推送外部通知」做成可靠的：失败自动重试（退避）→ 超过次数进死信；CRITICAL 级告警的推送可以延迟——理解死信与延迟消息是「业务可靠性」不是「中间件炫技」。
**要求**：

- 工程 = examples/ex02 的 pom；topic `alarm.alerts`，告警事件含 `alarmId/severity/sn/message`；`PushClient` 抽象（失败可注入，测试用假实现）
- 重试策略自实现：最多 3 次、退避间隔递增（如 1s、5s），第 3 次仍失败 → 投死信（写死信 topic `alarm.dlt` 或本地 DLQ 集合二选一，代码注释说明与 Kafka `.dlt` / RocketMQ `%DLQ%` / RabbitMQ DLX 的对应）
- 延迟消息：对照主文档 3.6，用「延迟级别 + 到期投递」模拟 CRITICAL 立即推、HIGH 延迟推（可参照 examples/ex03 的 availableAt 思路，不必真等）
- 纯逻辑部分配 JUnit：恒失败 3 次后进死信不无限重试；第 2 次成功时 attempts=2

**验收**：参考实现实测 `Tests run: 4`；能说出「无限重试会拖死消费者，直接丢弃会丢告警，死信是折中」以及本设计与 RocketMQ 原生重试/死信的差异。

## 练习 4：日志搜索（★★★）

**目标**：设计日志索引并写出检索代码——「最近 1 小时 order-service 的 ERROR 日志，按关键词相关性排序」，理解 text/keyword/date 的映射取舍与 bool 查询。
**要求**：

- 工程 = examples/ex05 的 pom；索引 `app-logs`，映射：`message` text（全文检索）、`level`/`service` keyword（精确过滤/聚合）、`ts` date
- 实现三个查询（Java client 或 REST DSL 都写一份对照）：① service=order-service 且 level=ERROR 且 ts 在最近 1 小时，按 ts 倒序；② message 含关键词（match，相关性排序）；③ 按 level 分组统计条数（terms 聚合）——三个查询对应主文档 3.9 的 match/term/range/bool/aggs
- 写 5 条以上样例日志（不同 service/level/时间）验证查询结果符合预期
- 能说出：为什么 level 用 keyword 不用 text、为什么「最近 1 小时」用 range 不用 match、聚合查询与 SQL `GROUP BY` 的对应

**验收**：参考实现实测三个查询输出符合预期（样例数据手算可核对）；能解释「ES 是最终一致的查询视图，主库在 MySQL，同步用 MQ + 对账」为什么是架构结论（主文档 3.10）。
