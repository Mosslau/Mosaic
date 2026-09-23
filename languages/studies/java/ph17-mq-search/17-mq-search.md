# Java 消息队列与搜索阶段

> 面向高并发系统，本阶段把 ph16 微服务阶段埋下的三条伏笔收口：用消息队列做异步削峰与解耦（Kafka / RocketMQ / RabbitMQ 三选一），用 Elasticsearch 做日志与业务检索——先会选型、会用 API、能设计可靠链路，再看底层原理。

## 1. 概述

本阶段是 Java 学习路线从「会拆服务」到「能扛流量」的中间站。roadmap 第 17 节目标：**掌握高并发系统常用中间件**。ph15 Spring 全家桶阶段攒下单体、[ph16 微服务与分布式阶段](../ph16-microservices/16-microservices.md)拆出服务，拆完之后一个立刻出现的问题：服务之间除了同步 HTTP 还能怎么协作？——答案之一就是消息队列：**调用方不等结果直接返回，把事件交给 MQ，由消费方异步处理**。这带来削峰（把洪峰摊平）、解耦（生产与消费各自演进）、异步化（慢操作挪出请求链路）三种能力；同时搜索是另一类高并发系统的标配——MySQL 的 `LIKE '%词%'` 在小数据量下够用，数据上了量、要按相关性排序、要做词级匹配时，需要 Elasticsearch 这类基于**倒排索引**的检索引擎。

ph16 的「下一阶段」预告里埋了三条线索，本阶段逐一收口：**Saga 补偿失败的异步重投**（MQ 重试 + 死信队列）、**本地消息表的异步投递**（RocketMQ 事务消息 / Kafka 事务 + Outbox 模式）、**削峰解耦**（roadmap 示例链路：`业务服务 → Kafka → 消费服务 → Elasticsearch`——正是本阶段 project 的设备事件搜索系统）。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 消息队列选型 | Kafka / RocketMQ / RabbitMQ 三款的架构模型、定位差异、对比表与选型建议 |
| 消息可靠性 | 生产者 ack/retry/幂等、broker 持久化与副本（ISR）、消费者 offset 与手动提交 |
| 幂等消费 | 为什么重复消费不可避免、at-least-once / at-most-once / exactly-once、去重方案（唯一约束/去重表/状态机） |
| 顺序性 | 全局顺序 vs 分区顺序、按 key 路由、重试破坏顺序的补救 |
| 死信与延迟 | 三款 MQ 的死信机制（DLT / %DLQ% / DLX）与延迟消息实现 |
| Elasticsearch | 倒排索引原理、分词与分析器、映射 Mapping、查询 DSL、写入链路、与 MySQL 定位差异 |
| 日志检索架构 | 业务日志 → Kafka → 消费清洗 → ES → 检索的典型链路，衔接 ph16 的异步与一致性话题 |

这个阶段只涉及**消息中间件与检索引擎的「用」与「原理」**：会配客户端、会写生产/消费/检索代码、能解释可靠性与一致性的取舍，**不涉及 Kafka 集群的运维与调优参数全集**（分区数规划、broker 配置调优、JMX 指标体系、滚动升级——[ph19 DevOps 与部署阶段](../ph19-devops-deploy/19-devops-deploy.md)）、**不涉及 ES 集群的分片规划、节点角色与性能调优**（同样是 [ph19 DevOps 与部署阶段](../ph19-devops-deploy/19-devops-deploy.md)；本阶段只在单机 docker 容器上跑通 API）、**不涉及缓存与高并发架构**（Redis 缓存三兄弟、限流、秒杀、连接池——[ph18 缓存与高并发阶段](../ph18-cache-concurrency/18-cache-concurrency.md)；本阶段提到的 Redis 只出现在「去重表」这种可选方案里，不展开）、**不涉及 MQ/ES 背后的网络编程与 JVM 并发底层**（Netty 之类的通信细节——[ph20 高级 Java 阶段](../ph20-advanced-java/20-advanced-java.md)）、**不涉及数据平台方向的组合应用**（[ph21 数据平台 / 数据中心后端方向 Java 阶段](../ph21-data-platform/21-data-platform.md)；本阶段的设备数据消费练习只到「消费 + 处理」为止）。也不重复 ph15 已讲的 Spring 容器/AOP/事务（本阶段每个消费者仍是那套单体结构），以及 ph16 已讲的 Saga/TCC/幂等键（本阶段在消息语义上复用其结论：**补偿要幂等、重试要幂等**）。

## 2. 来源与演变

消息队列的思想比互联网还老——**排队就是削峰**。1998 年 Sun 发布 JMS 规范（Java Message Service，点对点 Queue + 发布订阅 Topic 两种模型，定义了后来所有消息系统的词汇表），但 JMS 只是「接口标准」，实现（ActiveMQ 等）仍是单体 broker、吞吐有限、路由模型僵化。转折发生在三件事：2007 年 RabbitMQ 用 **AMQP 0-9-1 协议**把「路由」做成了第一公民（Exchange 按规则把消息分发给队列，Broker 不再是管道而是交换机）；2011 年 LinkedIn 开源 **Kafka**——它不把消息当「待办事项」而是当「可重放的日志流」（**设计哲学一句话加粗：消息不是发出去就没了，而是可以被多个消费者按自己的节奏反复消费的日志**），用分区 + 顺序写盘换来了百万级吞吐；2012 年阿里把内部 MetaQ 演进为 **RocketMQ**，针对电商场景补上了 Kafka 当时缺的「事务消息」「延迟消息」「消费重试」等金融级可靠性能力，2016 年捐给 Apache。这三家的定位差异至今仍是选型的起点。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| JMS 1.0 / 1.1（Sun） | 1998 / 2002 | Java 消息中间件的接口标准：Queue/Topic、事务性会话 |
| RabbitMQ 首发 | 2007 | AMQP 0-9-1：Exchange 路由模型、Erlang 高并发运行时 |
| Kafka 立项并开源 | 2008~2011 | LinkedIn 分布式提交日志；2012 进 Apache，分区 + 消费组 + 高吞吐 |
| RocketMQ 内部成形 | 2012 | 阿里 MetaQ 2.0 更名 RocketMQ，补事务消息/延迟消息/重试 |
| RocketMQ 进 Apache | 2016 | 2017 孵化、2020 毕业；国内电商场景事实标准之一 |
| Kafka 3.3+ / KRaft | 2022 | 元数据管理从 ZooKeeper 迁往自研 KRaft（Raft 协议），简化运维 |
| RocketMQ 5.0 | 2022 | 主推 Controller 高可用 + Proxy + 新 gRPC 客户端 rocketmq-client-java |
| Elasticsearch 8.0 | 2022 | 默认开启安全、移除 RestHighLevelClient、官方 Java API Client（elasticsearch-java） |

搜索一侧的谱系更老：1999 年 Doug Cutting 写 Lucene，确立**倒排索引**作为全文检索的核心数据结构（几十年未变）；2004 年 CNET 在 Lucene 之上做 Solr 并捐给 Apache，是 2010 年前的检索事实标准；2010 年 Shay Banon 发布 **Elasticsearch**——把 Lucene 包成**分布式 + RESTful** 的搜索引擎（存进去的是 JSON 文档，查出来的是 HTTP 响应），2011 年起在日志检索（ELK：Elasticsearch + Logstash + Kibana）领域爆发。ES 版本演进有一个大跳跃（1.x → 2.x → 5.x，2016 年与全家桶版本对齐），此后：6.0 弃用 mapping type、7.0 移除 type 并把默认分片数降为 1、8.0（2022）默认开启安全并把 Java 客户端换代为 `elasticsearch-java`（老 TransportClient 与 RestHighLevelClient 均移除）。

> 本阶段只用 ES 8.x 的新客户端与 REST API；**集群部署、分片规划与调优属 [ph19 DevOps 与部署阶段](../ph19-devops-deploy/19-devops-deploy.md)**，这里只需在 docker 容器里把 API 跑通。

本文示例以 **Kafka 3.7 / RocketMQ 5.x（概念基线）/ RabbitMQ 3.x（概念基线）/ Elasticsearch 8.x** 为基线（选择理由：Kafka 与 ES 是 roadmap 示例链路的主件，且 Kafka 3.x 与 ES 8.x 正是当前生态的长期稳定线；RocketMQ/RabbitMQ 本阶段只讲机制与代码片段，不跑工程）。验证工具链 **OpenJDK 17 + Maven 3.9 + Spring Boot 3.3.0**（与 ph14/ph15/ph16 完全同基线），Kafka 用 **kafka-clients 3.7.0** 与 **spring-kafka 3.2.0**（Boot 3.3.0 依赖管理默认版本），ES 用 **co.elastic.clients:elasticsearch-java 8.x**。**本环境未运行任何中间件**：examples/project 中依赖真 Kafka/ES 的代码全部标注「未在本环境验证」，需要时用 `docker compose` 起服务后按命令验证（见各 README）；两个纯 Java 教学片段（ex03 死信/延迟、ex04 手写倒排）已在 OpenJDK 17 本机实测通过并标注「已验证」。消息队列与检索的「三个环节、两种一致性」心智模型十年未变——变的是版本号，不变的是「可靠投递靠哪几层、幂等为什么必须设计在消费端」。

## 3. 语法与参数

### 3.1 消息队列核心模型与三款 MQ 对比

先把词汇表钉死——三款 MQ 概念大同小异，只是叫法不同：

| 概念 | Kafka | RocketMQ | RabbitMQ |
|------|-------|----------|----------|
| 消息容器 | Topic 分 Partition | Topic 分 MessageQueue | Queue（经 Exchange 绑定） |
| 消息顺序边界 | 单分区内有序 | 单队列内有序 | 单队列内有序（单消费者） |
| 消费单位 | 消费组（group）内分区被组员瓜分 | 消费组内队列被组员瓜分（集群模式） | 队列被多个消费者瓜分（同一队列） |
| 拉/推 | 拉（poll）为主 | 拉为主（长轮询） | 推（basicDeliver，可配 prefetch） |
| 吞吐量级 | 最高（分区并行 + 顺序写盘） | 高 | 中（路由灵活、功能最全） |
| 典型场景 | 日志/事件流、大数据管道 | 电商订单、金融可靠投递 | 业务集成、路由复杂的通知 |

Kafka 的最小拓扑（一张图记住「消息从哪来、存在哪、谁消费」）：

```text
生产者 ──send──▶ Topic「orders」                     消费者组「order-group」
                  ├─ partition 0: [msg0][msg1][msg2] ◀── consumer-A（负责 0、2 分区）
                  ├─ partition 1: [msg3][msg4]      ◀── consumer-B（负责 1 分区）
                  └─ partition 2: [msg5]            ◀── consumer-A
    消息在分区内按 offset（0,1,2,…）顺序追加；消费组内分区不重复分配，
    同一条消息只会被组内一个消费者处理——组是「队列语义」，不同组是「发布订阅语义」
```

**分区的两个作用**（roadmap 必会概念「分区影响顺序和吞吐」）：① 并行单元——topic 分成 N 个分区，生产者可并发写、消费者组内 N 个消费者可各领一个分区并行消费，吞吐随分区数近似线性增长；② 顺序边界——**分区内严格有序，分区之间不保证顺序**。所以「要顺序就按 key 进同一分区（3.5），要吞吐就多分区并行（但放弃跨分区顺序）」。

三款 MQ 定位差异要能说清楚（对照 ph16 的选型语境）：**Kafka** 把消息当「流」，设计目标是日志级吞吐与多消费者重放，代价是功能少（无原生延迟消息/死信，见 3.6）；**RocketMQ** 是 Kafka 的「电商版」——同样分区模型，但补了事务消息、延迟消息、消费重试、死信队列等业务可靠性能力，国内订单/交易场景事实标准；**RabbitMQ** 走 AMQP 路由模型，Exchange 让「一条消息按规则进多个队列」变得自然，吞吐低于前两者但功能灵活、生态老牌，适合中小流量下的复杂业务路由。

> MQ 选型没有全能的：**大数据/日志/事件流首选 Kafka，电商交易强可靠首选 RocketMQ，路由复杂的中小系统 RabbitMQ 足够**——本阶段 project 用 Kafka 落地 roadmap 示例链路，主文档 5 章有完整选型表。

### 3.2 Kafka 生产者与消费者（kafka-clients 骨架）

Kafka 客户端坐标是 `org.apache.kafka:kafka-clients`（Java 官方客户端，spring-kafka 底层也是它）。生产者核心是三个概念：**序列化器**（key/value 字节化）、**acks**（写成功要 broker 确认到哪一层）、**回调**（send 是异步的，结果在回调里看）：

```java
// examples/ex01-kafka-clients-basic/.../ProducerMain.java —— Kafka 生产者骨架（未在本环境验证）
Properties props = new Properties();
props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
props.put(ProducerConfig.ACKS_CONFIG, "all");                    // 3.3：写可靠性
props.put(ProducerConfig.RETRIES_CONFIG, Integer.MAX_VALUE);     // 瞬时故障无限重试（幂等前提下安全）
props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);       // Kafka 3.x 默认开；开则 acks 强制 all
try (KafkaProducer<String, String> producer = new KafkaProducer<>(props)) {
    ProducerRecord<String, String> record = new ProducerRecord<>("orders", orderId, orderJson);
    producer.send(record, (metadata, exception) -> {   // send 不阻塞；结果异步回调
        if (exception != null) log.error("发送失败 orderId={}", orderId, exception);
        else log.info("已写入 topic={} partition={} offset={}", metadata.topic(),
                metadata.partition(), metadata.offset());
    });
}
```

消费者与生产者最大的不同：它要**自己维护「读到哪里了」**（offset）。Kafka 把 offset 存在 broker 的 `__consumer_offsets` 内部主题里，按「消费组」隔离；组内协调者负责把 topic 的分区分配给组员（4.2 重平衡）。可靠消费的标准姿势是**关自动提交、处理成功再手动提交**：

```java
// examples/ex01-kafka-clients-basic/.../ConsumerMain.java —— 手动提交 offset（未在本环境验证）
props.put(ConsumerConfig.GROUP_ID_CONFIG, "ex01-order-group");
props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest"); // 组无已提交 offset 时从最早开始
props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);     // 关自动提交，由代码决定何时算「处理完」
try (KafkaConsumer<String, String> consumer = new KafkaConsumer<>(props)) {
    consumer.subscribe(List.of("orders"));
    while (running) {
        ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(500)); // 拉一批
        for (ConsumerRecord<String, String> record : records) {
            process(record);                    // 1. 先处理业务（幂等地）
            lastProcessed.put(new TopicPartition(record.topic(), record.partition()),
                    new OffsetAndMetadata(record.offset() + 1)); // 2. 记下「下一条要读的 offset」
        }
        consumer.commitSync();                  // 3. 批量提交：这批全成功才推进
    }
}
```

生产实践里更常用 spring-kafka 的注解式写法（Boot 自动配置 `KafkaTemplate` 与监听容器，`spring.kafka.*` 见 ex02）：

```java
// examples/ex02-spring-kafka-idempotent-consume/.../OrderCreatedConsumer.java —— 注解式消费（未在本环境验证）
@KafkaListener(topics = "orders", groupId = "order-created-group") // 与上面手动版同语义
public void onMessage(ConsumerRecord<String, String> record, Acknowledgment ack) {
    OrderEvent event = objectMapper.readValue(record.value(), OrderEvent.class);
    if (dedup.tryAcquire(event.orderId())) {    // 3.4：消费端幂等去重
        orderService.markCreated(event);        // 业务处理（建单/扣库存……）
    }
    ack.acknowledge();                          // application.yml: spring.kafka.listener.ack-mode=MANUAL
}
```

裸客户端与 spring-kafka 是一一对应的，记住映射就能在两套写法间自由切换（spring-kafka 的配置前缀统一走 `spring.kafka.*`，Boot 自动配置把这些属性翻译成上面的 `Properties`）：

| kafka-clients 配置 | spring-boot 配置 | 默认 | 本阶段建议 |
|-------------------|-----------------|------|-----------|
| `bootstrap.servers` | `spring.kafka.bootstrap-servers` | — | `localhost:9092`（本阶段 docker） |
| `acks` | `spring.kafka.producer.acks` | all（3.x） | `all` |
| `enable.idempotence` | `spring.kafka.producer.properties.enable.idempotence` | true（3.x） | 默认开即可 |
| `group.id` | `spring.kafka.consumer.group-id` | — | 按业务组命名（如 `order-created-group`） |
| `enable.auto.commit` | `spring.kafka.consumer.enable-auto-commit` | true | **false**（改手动提交） |
| `auto.offset.reset` | `spring.kafka.consumer.auto-offset-reset` | latest | 教学用 `earliest`（不丢演示数据） |
| 容器提交方式 | `spring.kafka.listener.ack-mode` | batch | `MANUAL`（监听方法收 `Acknowledgment` 自己提交） |

**消息内容与序列化**：本阶段示例统一用 JSON 字符串（人类可读、好排查）；生产上的序列化选型——JSON 方便、Avro/Protobuf 带 schema 演进与压缩（配 Schema Registry），字符串拼接在代码评审里基本会被否。序列化器只在客户端声明（`StringSerializer`），broker 不校验格式——**消息格式的兼容性由生产/消费双方契约保证，Kafka 不管**（这也是「先定契约再上 MQ」的工程纪律）。

**Topic 创建**：Kafka 没有「建表」概念，`send` 时 topic 不存在会按 broker 的 `auto.create.topics.enable`（默认开）自动创建，默认 1 分区 1 副本——本阶段单机演示够用；正式的分区/副本规划属 ph19。

### 3.3 消息可靠性：三个环节逐个攻

消息从生产到消费要过三个环节，可靠性必须分段看，任何一段都可能丢：

| 环节 | 丢消息的可能 | 防御手段 | 对应配置/机制 |
|------|-------------|---------|--------------|
| 生产者 → broker | 网络超时后没确认；broker 写失败 | 重试 + 等待确认 + 幂等去重 | `acks=all`、`retries`、`enable.idempotence` |
| broker 存储 | 进程崩溃、磁盘坏 | 落盘 + 副本冗余 | Kafka 副本 ISR（4.1）、RocketMQ 刷盘/主从、RabbitMQ 持久化 + 镜像/仲裁队列 |
| broker → 消费者 | 处理完提交前崩溃（重复）；提交后处理中崩溃（丢失） | 消费端自己定「先处理还是先提交」 | `enable.auto.commit=false` 手动提交 |

**生产端：acks 三档**——`acks=0` 发出去就算成功（可能丢，仅日志类可接受）、`acks=1` leader 写盘即确认（leader 挂了可能丢）、`acks=all`（`-1`）ISR 全部确认才算成功（配合 `min.insync.replicas=2` 才是真正的不丢）。**重试**解决「瞬时故障」（网络抖动、leader 选举），但重试 + 不幂等 = 重复写入——所以 Kafka 3.x 默认开启**幂等生产者**（`enable.idempotence=true`：给每条消息标 PID + 序列号，broker 侧去重），它要求 `acks=all` 且 `max.in.flight.requests.per.connection ≤ 5`，一次会话内的重试不会产生重复记录。跨会话的精确一次（事务）见 4.1。

**消费端：offset 语义三兄弟**（面试高频，也是 roadmap 必会概念「消费者要设计幂等」的根源）：

| 语义 | 做法 | 后果 |
|------|------|------|
| at-most-once（至多一次） | 先提交 offset 再处理 | 崩溃丢消息（处理没跑完）——仅对「丢了无所谓」的指标类消息 |
| at-least-once（至少一次） | 先处理再提交（手动提交的标准姿势） | **可能重复处理**——大部分业务系统的默认选择 |
| exactly-once（精确一次） | 事务 + 幂等消费 / 下游幂等 | 工程上 ≈「at-least-once + 消费端幂等」 |

结论先记住：**任何「不丢」的方案最终都落到 at-least-once，于是重复不可避免，幂等必须设计在消费端**（3.4）。自动提交（`enable.auto.commit=true`）默认每 5 秒提交一次，崩溃时窗口内的消息会被重复消费——生产环境一律关掉手动提交。生产端配置速查（三款 MQ 逐项对得上，Kafka 列是默认口径，RocketMQ/RabbitMQ 概念同义、配置名不同）：

| 可靠性诉求 | Kafka | RocketMQ | RabbitMQ |
|-----------|-------|----------|----------|
| 等 broker 确认 | `acks=all` | 同步发送 + 发送结果校验 | publisher confirm 模式 |
| 瞬时故障重试 | `retries`（幂等开时建议大值） | 生产者重试（默认 2 次） | confirm 失败由发送方重发 |
| 写重复防护 | 幂等生产者（PID+seq 去重） | 生产者侧无，靠消费幂等 | 无，靠消息 id + 消费幂等 |
| 服务端持久化 | 副本 ISR + segment 落盘 | 刷盘策略（同步/异步）+ 主从复制 | 队列/消息 durable + 镜像/仲裁队列 |
| 极端不丢组合 | `acks=all` + `min.insync.replicas=2` | 同步刷盘 + 同步复制 | confirm + durable + 仲裁队列多数派 |

这张表的读法：**没有任何一行能单独保证不丢，丢不丢是「确认层级 × 存储冗余 × 消费提交」的组合结果**——与本阶段所有可靠性结论一致：可靠性是设计出来的分层防御，不是某个开关。

### 3.4 重复消费与幂等去重

为什么 Kafka 一定会有重复？三个来源：① 生产者重试（同一条可能写了两遍，幂等生产者只解决会话内）；② 消费者处理成功后、提交 offset 前崩溃（重启从旧 offset 重读）；③ 重平衡把分区转给别的消费者（3.5 会说顺序也被它打断）。**既然重复不可避免，消费端就必须能识别「这条我处理过了」**。

| 去重方案 | 原理 | 适用/注意 |
|---------|------|----------|
| 数据库唯一约束 | 用业务唯一键（orderId/sn+seq）建唯一索引，重复插入被数据库拒 | **最可靠的兜底**，必须有，哪怕平时走缓存去重 |
| 去重表 / Redis SETNX | 处理前占位，已存在则跳过；TTL 控制窗口 | 快但窗口外的重复管不住（TTL 过期后重放）——只挡「近重复」 |
| 状态机迁移校验 | 事件携带目标状态，当前状态已是目标/更新则丢弃 | 处理「旧事件迟到」与乱序（3.5 配合 seq） |
| 幂等键 + 结果缓存 | 同 key 返回首次处理结果 | 面向接口层（ph16 ex04 的 Idempotency-Key 思路） |

代码落地（去重表的最小实现，生产建议换 Redis/数据库）：

```java
// examples/ex02-spring-kafka-idempotent-consume/.../DedupStore.java —— TTL 去重表（未在本环境验证）
public final class DedupStore {
    private final ConcurrentHashMap<String, Long> seen = new ConcurrentHashMap<>(); // key -> 过期时刻
    private final long ttlMillis;
    public boolean tryAcquire(String bizKey) {              // 返回 true = 首次见，可处理
        long now = System.currentTimeMillis();
        Long prev = seen.putIfAbsent(bizKey, now + ttlMillis);  // 原子占位（Redis SETNX 的同构）
        return prev == null || prev < now;                  // 过期重放也放行（数据库唯一键兜底）
    }
}
```

练习要能说清三层关系：**Redis/内存去重挡重复流量，数据库唯一约束是最终防线，状态机挡乱序**——三层各自解决不同来源的重复（网络重试、崩溃重放、迟到事件），与 ph16 幂等键的分层完全同构，只是从「请求层」移到了「消息层」。

### 3.5 消息顺序性：分区内有序 vs 全局有序

「顺序」在分布式消息里有两种口径，别混：

| 口径 | 含义 | 代价 |
|------|------|------|
| 全局顺序 | 所有消息严格按发送顺序消费 | 只能单分区 + 单消费线程，吞吐 = 单机单线程 |
| 分区顺序 | 同一 key（业务实体）的消息有序，不同 key 并行 | 吞吐高，但跨 key 顺序不保证 |

**默认姿势是分区顺序**：把业务实体 id 作为消息 key（Kafka 按 key 哈希路由分区、RocketMQ 用 MessageQueueSelector 选队列），同一订单/同一设备的所有事件进同一分区，该实体的处理有序，不同实体并行——「每实体顺序、整体并行」是吞吐与顺序的平衡点。Spring 侧 key 路由由 producer 的 `partitioner` 决定（默认 `murmur2(key) % partitionNum`，key 为 null 走 sticky 随机分区——**所以「要顺序就别让 key 为空」**）。

**顺序会被什么破坏**：① key 为 null 随机分区（同实体消息散到多个分区）；② 单分区内重试乱序——`max.in.flight.requests.per.connection > 1` 且未开幂等时，前一条失败重发可能排到后一条后面；③ 消费端多线程处理同一分区（一个分区被组内一个消费者拉取，但若该消费者内部再开多线程并发处理，顺序照样乱）；④ 重试失败后消息重新入队（RocketMQ 顺序消息失败会阻塞该队列直到成功，代价是队列卡住）。补救套路：消息里带业务 `seq`/版本号，消费端发现 `seq` 小于已处理的最大值就丢弃（迟到的旧消息）——这也是「消息必须包含业务时间戳/序号」的原因。

RocketMQ 的队列选择是显式的（Kafka 是 key 哈希、RocketMQ 把选择器交给你，语义等价——「同一个业务 key 永远进同一队列」）：

```java
// RocketMQ 顺序消息：按业务 key 选队列（未在本环境验证，需本地 NameServer+Broker）
SendResult result = producer.send(message, (mqs, msg, arg) -> {
    String bizKey = (String) arg;                       // 例如订单号/设备 sn
    int index = Math.abs(bizKey.hashCode()) % mqs.size(); // 同 key 恒进同一队列 → 该 key 有序
    return mqs.get(index);
}, "order-1001");
```

注意 `String.hashCode()` 可能为负，取绝对值前处理（`Math.abs(Integer.MIN_VALUE)` 仍是负）——顺序路由的 key 哈希在生产代码里是个常见小坑，Kafka 内部用 murmur2 没有这个问题，手写路由时别踩。

### 3.6 死信队列与延迟消息

死信与延迟是「业务可靠性」的标配，但三款 MQ 的实现路径完全不同，对照表记：

| 能力 | Kafka | RocketMQ | RabbitMQ |
|------|-------|----------|----------|
| 死信（处理不掉的消息去哪） | 无原生——消费失败的消息需要生产者/消费者自己发到 `xxx.dlt` 主题（spring-kafka 的 `DeadLetterPublishingRecoverer` 封装了这件事） | 原生：消费失败自动重试（默认 16 次，间隔递增），仍失败进 **`%DLQ%消费组名`** 死信主题 | 原生：**死信交换机 DLX**——消息被 nack 不 requeue、或 TTL 过期、或队列超限时，按 x-dead-letter-exchange 转投死信队列 |
| 延迟消息 | 无原生——需要业务侧设计（分层 topic + 定时重投，或用 RocketMQ 的 18 级延迟做兜底） | **原生 18 级延迟**：`1s/5s/10s/30s/1m/…/2h`，`Message.setDelayTimeLevel(n)` | 原生无——靠「消息 TTL + DLX」模拟（TTL 到期进死信队列=到期才消费），或官方社区插件 `rabbitmq_delayed_message_exchange` |
| 语义本质 | 一切自己拼 | 消费重试 + 死信内建 | 路由模型让「重投到哪」只是绑定规则 |

死信队列要回答的问题：**消息反复处理失败（比如下游 5xx 三天）不该无限重试占用消费者，也不该直接丢掉**——投进死信队列，由人工或对账任务（ph16 4.2 的「对账兜底」就是干这个的）定期处理。延迟消息要回答：**「30 分钟后还没支付就关单」这类定时业务，不该每个订单起一个定时器**——把消息标成 30 分钟后才可见即可。Kafka 侧的常见组合方案（无原生延迟时的通用套路）：

```text
main topic「orders」                    retry topic「orders.retry-5m」
  消费失败 ──▶ 判断：重试次数 < 上限？          定时任务到点把消息重新投回 main topic
                │是 → 投 retry topic（5 分钟后可见）  ▲
                │否 → 投 DLQ「orders.dlt」           │（spring-kafka RetryTopic / 自建重投线程）
                └────────────────────────────────────┘
```

spring-kafka 把这套封装成 `@RetryableTopic`（自动生成重试主题并配置延迟间隔）与 `DeadLetterPublishingRecoverer`（重试耗尽投 DLT），主文档 6 章 ex03 用纯 Java 实现了一版「延迟 + 死信」的语义模拟，方便不装 broker 也能看清流程。两行最小代码看清「延迟」与「死信」的 API 形态（均未在本环境验证）：

```java
// RocketMQ 延迟消息：18 级延迟级别，2 = 5 秒后可见（需本地 NameServer+Broker）
Message msg = new Message("order-topic", orderJson.getBytes(StandardCharsets.UTF_8));
msg.setDelayTimeLevel(2);                  // 1=1s 2=5s 3=10s … 18=2h；级别由服务端配置决定
producer.send(msg);                        // 消费者 5 秒后才拉得到

// RabbitMQ 死信：声明队列时指定死信交换机，nack(requeue=false) 或 TTL 过期的消息自动转投（需本地 broker）
Map<String, Object> args = new HashMap<>();
args.put("x-dead-letter-exchange", "dlx.order");          // 死信交换机
args.put("x-dead-letter-routing-key", "order.dead");
channel.queueDeclare("order-queue", true, false, false, args);
channel.basicNack(delivery.getEnvelope().getDeliveryTag(), false, false); // 不重回队列 → 进 DLX
```

读代码时注意「死信」的两层语义别混：**消费失败重试耗尽**（业务不要了，进死信）与**消息过期/超限**（时间或容量到了，进死信）——RocketMQ 的 %DLQ% 主要管前者，RabbitMQ 的 DLX 两者都管（TTL 过期正是延迟消息的实现基础），Kafka 两者都要自己写。

### 3.7 RocketMQ / RabbitMQ 特有机制速览

本阶段对两者的定位是「会选、能看懂、能写最小代码」，不跑工程（客户端坐标见下，均未在本环境验证）：

**RocketMQ（org.apache.rocketmq:rocketmq-client，5.x 新客户端为 rocketmq-client-java）** 相对 Kafka 的三个补强正是 roadmap 关注点：① **事务消息**——发「半消息」后先执行本地事务，成功后 commit（消息才可见）、失败 rollback，超时由 broker 反向**回查**生产者本地事务结果——这是 ph16 本地消息表的中间件原生版（本地消息表：本地事务写消息表 + 异步投递；事务消息：broker 帮你做了「半可见 + 回查」，两者二选一，见 4.1）；② **延迟消息**（18 级，3.6 表）；③ **消费失败重试 + 死信**（默认重试 16 次进 `%DLQ%消费组`）。消费分**集群模式**（队列被组员瓜分，每条只消费一次）与**广播模式**（每个组员都消费全量——配置变更通知类场景）。

**RabbitMQ（spring-boot-starter-amqp / com.rabbitmq:amqp-client）** 的核心是 **Exchange**：消息不是直接进队列，而是发给交换机，交换机按 binding 规则（direct 精确 routingKey / topic 通配 / fanout 广播 / headers）投到 0~N 个队列——「一条消息按规则扇出给多组消费者」是它的天然强项。可靠性三件套：生产者 **confirm** 模式（broker 确认收到）、队列+消息**持久化**（重启不丢）、消费者**手动 ack**（处理成功才 `basicAck`，失败 `basicNack(requeue=false)` 转死信）。吞吐上限低于 Kafka（Erlang 单节点几万级 vs Kafka 单分区百万级），但功能灵活、运维简单，中小流量首选。

### 3.8 Elasticsearch：文档、映射与分词

ES 的三层心智：**存进去的是 JSON 文档，组织方式是索引（类似数据库的表，但 schema 是「映射」而非建表），查询走 REST/客户端 DSL**。Java 侧坐标是 `co.elastic.clients:elasticsearch-java`（8.x 官方客户端，底层走 REST；老 RestHighLevelClient 已移除）。「字段存成什么样、怎么被检索」由 **Mapping（映射）** 决定，与 MySQL 建表类比：

| ES 概念 | MySQL 类比 | 本阶段要点 |
|---------|-----------|-----------|
| index（索引） | 表 | 文档的集合，默认 1 主分片 + 1 副本 |
| mapping | 表结构 | 定义每个字段的类型与分析方式 |
| document | 行 | 一条 JSON |
| field type: text vs keyword | — | **text 会分词（全文检索），keyword 不分词（精确匹配/排序/聚合）**——最常配错的点 |
| query DSL | SQL | JSON 风格的查询体 |

创建索引 + 映射的 REST 原语（Java client 同义，见 ex05）：

```json
PUT /logs
{
  "mappings": {
    "properties": {
      "message": { "type": "text", "analyzer": "standard" },
      "level":   { "type": "keyword" },
      "service": { "type": "keyword" },
      "ts":      { "type": "date" }
    }
  }
}
```

**分词是检索正确性的第一道关**：`message` 声明 `text` 后，写入时 ES 用分析器把它切成词项（term）再进倒排索引。分析器 = 三段管线：**character filter**（字符预处理）→ **tokenizer**（切词，`standard` 按 Unicode 规则切、`whitespace` 按空白切）→ **token filter**（小写化、去停用词、词干化）。同一句话在不同分析器下进索引的词项完全不同：

```text
输入: "Kafka Consumer Timeout 2026-09-01 12:00"
standard 分析器（默认，小写化后）→ [kafka][consumer][timeout][2026][09][01][12][00]
keyword 分析器（不分词）           → ["Kafka Consumer Timeout 2026-09-01 12:00"]（整串一个词项）
```
「查询文本也要走同一分析器」的推论：`match "Kafka"` 能命中上面的文档（kafka 在词项表里），`term "Kafka"` 却查不到（词项表里是小写 `kafka`），`term` 查整句更是必然落空——分析器决定了 match 与 term 的行为差异（3.9 表）。

默认 `standard` 分析器适合英文；**中文整句没有空格，`standard` 会把「电动补能电」切得七零八落**，生产中文检索要装 ik 等中文分词插件（本阶段 project 的 message 用英文/拼音字段演示即可，中文分词插件安装不在本阶段展开）。查询时同样的文本也要过分析器——「查询词怎么分词」与「索引词怎么分词」必须一致，这是 match 查询与 term 查询的根本区别（3.9）。

### 3.9 Elasticsearch：查询 DSL 与 Java client

四种基础查询先分清楚（面试与写 DSL 的地基）：

| 查询 | 是否分词 | 语义 | 典型用例 |
|------|---------|------|---------|
| `match` | 是（查询文本先分词） | 全文匹配，任一词项命中即中，可算相关性分 | 搜日志 message 里的关键词 |
| `term` | 否（整词精确） | 精确匹配单个词项 | level=ERROR、service=order-service（keyword 字段） |
| `range` | — | 范围匹配 | `ts` 在最近 1 小时 |
| `bool` | — | must（且）/ should（或，加分）/ must_not（非）/ filter（且，不算分） | 组合查询的主干 |

```json
GET /logs/_search
{
  "query": {
    "bool": {
      "must":     [ { "match": { "message": "kafka timeout" } } ],
      "filter":   [ { "term":  { "level": "ERROR" } },
                    { "range": { "ts": { "gte": "now-1h" } } } ]
    }
  },
  "sort":  [ { "ts": "desc" } ],
  "from": 0, "size": 20
}
```

Java client 是同一 DSL 的类型安全版（lambda 构建器，与 3.8 的 REST 一一对应）：

```java
// examples/ex05-elasticsearch-java-client/.../EsSearchDemo.java 摘录 —— 传输层装配 + bool 查询（未在本环境验证）
RestClient restClient = RestClient.builder(new HttpHost("localhost", 9200)).build();
ElasticsearchTransport transport = new RestClientTransport(restClient, new JacksonJsonpMapper());
try (ElasticsearchClient es = new ElasticsearchClient(transport)) {   // 8.x 官方客户端标准装配
    SearchResponse<LogDoc> resp = es.search(s -> s
            .index("logs")
            .query(q -> q.bool(b -> b
                    .must(m -> m.match(t -> t.field("message").query("kafka timeout")))
                    .filter(f -> f.term(t -> t.field("level").value("ERROR")))))
            .sort(o -> o.field(f -> f.field("ts").order(SortOrder.Desc))),
            LogDoc.class);                                       // 反序列化为 record
    for (Hit<LogDoc> hit : resp.hits().hits()) {
        log.info("score={} doc={}", hit.score(), hit.source());  // _score 相关性分（match 才有意义）
    }
}
```

补充三个高频注意点：① **`term` 查 text 字段基本查不到**——text 已被分词，索引里没有整串词项；对 text 做精确词匹配要用 `keyword` 子字段或 keyword 类型字段；② 默认 `from+size` 分页上限 10000（`index.max_result_window`），深分页用 `search_after`/scroll（大数据量遍历的场景）；③ **聚合**（`aggs`）在索引上做分组统计，等价 SQL 的 `GROUP BY`——日志检索里「按 level 统计各等级条数」就是 terms 聚合，一个 bucket 遍历 O(词项) 而非扫全表。

### 3.10 与 MySQL 的定位差异、索引同步一致性

**ES 不是数据库的替代品，是「检索」的补充**——把两者的定位差异钉死，才能理解为什么「搜索索引要考虑同步一致性」（roadmap 必会概念）：

| 维度 | MySQL | Elasticsearch |
|------|-------|---------------|
| 事务 | ACID 事务、行锁 | 无跨文档事务，近实时（默认 1s 内可见） |
| 更新 | 就地更新 | 文档整体替换（segment 不可变，见 4.3） |
| 模糊/全文检索 | `LIKE '%x%'` 全表扫、无相关性排序 | 倒排索引 + 相关性打分，毫秒级 |
| 聚合分析 | GROUP BY（count 量级大时吃力） | terms/date_histogram 聚合，为分析而生 |
| 定位 | 系统记录事实的主存储（source of truth） | 面向查询的「副本」（query-focused view） |

**主存储的写入怎么同步到 ES？** 数据双写一致性是架构题（ph16 4.2 的「最终一致」在这里再次出现）：

| 方案 | 流程 | 一致性 | 备注 |
|------|------|--------|------|
| 同步双写 | 业务代码同时写 MySQL 与 ES | 强一致但耦合、慢 | 小系统可用；失败要回滚/补偿，别当真方案 |
| **MQ 异步双写（本阶段方案）** | 业务写库 → 发事件到 Kafka → 消费服务写 ES | 最终一致（秒级） | **roadmap 示例链路**：业务服务 → Kafka → 消费服务 → ES；消费失败走重试/DLQ（3.6），对账兜底 |
| CDC（变更数据捕获） | 监听 binlog → 解析 → 写 ES | 最终一致 | 用现成管道（Canal/Logstash JDBC 等），细节属 ph13/ph19 的工具侧 |

工程结论：**把 ES 当「最终一致的查询视图」，主库永远是 MySQL；同步用 MQ 削峰解耦 + 消费重试兜底，必要时定时对账**——这正是本阶段 project（设备事件 → Kafka → 消费 → ES）要演示的完整形态。

## 4. 底层原理

### 4.1 Kafka 存储模型与副本机制：ISR / AR / 高水位

Kafka 高性能的根在存储设计：每个分区是一个 **append-only 日志**，消息只追加不修改；日志按大小/时间切成 **segment 文件**（活跃段写、老段只读可删），段内每条消息有唯一 offset。顺序追加写充分利用**页缓存与顺序 I/O**，读侧靠页缓存命中 + **零拷贝（sendfile）** 把数据直接送网卡——「把随机写变成顺序写、把内存拷贝省掉」，这是单分区百万级吞吐的秘密。**Kafka 的可靠性与性能的取舍都在「副本怎么同步」上**：

```text
topic「orders」分区 0 的三副本（AR = 分配给该分区的全部副本）
  leader（broker-1）: 收生产者的写
  follower（broker-2）: 从 leader 拉取同步   ← 在 ISR（in-sync replicas，跟得上进度的副本集合）内
  follower（broker-3）: 落后太多被踢出 ISR     ← 只剩 leader 在 ISR 时，acks=all + min.insync.replicas=1 等于没防
```

关键概念钉死：**AR（assigned replicas）** = 该分区分配到的全部副本；**ISR（in-sync replicas）** = 其中与 leader 保持同步的子集（落后超过 `replica.lag.time.max.ms` 被踢出，追上了再加回）；**acks=all 等的是 ISR 全员确认**，所以生产要配 `min.insync.replicas=2` 才是真不丢（ISR 少于它时生产者报 `NotEnoughReplicas` 而非悄悄丢）；**高水位（HW）与 LEO（log end offset）**——HW 是 ISR 中已同步的偏移位，消费者只能读到 HW 以下的已提交消息，保证「leader 挂了换人后不会读出没同步完的消息」（这也解释了「acks=1 为什么可能丢」：leader 独有但未进 HW 的数据随 leader 消失）。

生产者的**幂等与事务**是 3.3 的底层版：幂等生产者给每条消息打 `(PID, 序列号)`，broker 按序列号去重，保证「一次会话内重试不重复」；**事务**（`initTransactions`/`beginTransaction`/`commitTransaction`，消费端 `isolation.level=read_committed`）把「写多个分区 + 提交消费 offset」包成原子——这正是 **Outbox 模式**的载体：业务事务里写一张 `outbox` 表（本地消息表，ph16 3.4 的伏笔），事务提交后由「事务生产者」把 outbox 行发到 Kafka，再删 outbox 行；与 RocketMQ 事务消息（3.7）是同一问题的两种解法——**一个用中间件原生半消息，一个用本地表 + 事务，都保证「业务与消息要么都成要么都没」**。注意：Kafka 事务保证的是「写入多个分区的原子性」，**消费端的重复处理仍要幂等兜底**（exactly-once 的完整链条必须两端配合）。

### 4.2 消费组与重平衡：协调者、分配策略、STW 代价

消费组的调度中枢是 **group coordinator**（某个 broker 上，按组名哈希选）；它维护组员心跳、决定分区归属。流程：组员启动 → 向 coordinator **JoinGroup**（报自己要订阅的 topic）→ coordinator 选 leader 组员 → 组 leader 用分配策略算出「谁拿哪些分区」→ **SyncGroup** 分发结果 → 组员开始 poll。分区变化、组员增减都会触发新一轮 **rebalance（重平衡）**——而 rebalance 的代价是**整个组暂停消费**（所有组员 revoke 旧分区、重新分配、再从头拉），一个消费者的抖动会拖停全组，这正是「消息积压需要监控」的机制源头之一。

| 分配策略（`partition.assignment.strategy`） | 做法 | 问题 |
|------|------|------|
| Range（默认之一） | 按主题逐个把分区均分给组员 | 组员数变化时重分配面大 |
| RoundRobin | 全部分区轮流分发 | 同上 |
| Sticky（默认） | 尽量保持上次分配，只挪有变化的分区 | 减少重平衡的移动面 |
| CooperativeSticky | 增量式重平衡（KIP-429） | 允许边消费边调整，不停全组 |

**静态成员（`group.instance.id`，KIP-345）**：给消费者起固定实例名，短暂断开（如 GC/发布）不触发 rebalance，直接等它回来——解决「消费者一抖动全组停摆」的工程问题。还有两个与 rebalance 强相关的消费者参数要理解：`max.poll.interval.ms`（默认 5 分钟）——**单次 poll 循环里处理太久会被判死踢出组**，所以重处理（批量/长任务）要拆批或改用别的消费模式；`session.timeout.ms`/`heartbeat.interval.ms`（心跳判活）。**积压（lag）** = 生产 offset - 消费 offset：`kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group <组>` 能看每分区 lag，监控平台定期拉这个值、超阈值告警——**扩容消费者前先确认分区数够不够**（消费者数 > 分区数时多余消费者空转）。

### 4.3 Elasticsearch 的倒排索引、分析器与写入链路

**倒排索引 = 词项 → 文档列表**。正排（MySQL 行式存储）是「文档 → 字段」，查「哪些文档含 kafka」得全表扫；倒排把「哪个词出现在哪些文档」预先算好存成表，查询变成一次词典查找 + 一次链表合并：

```text
文档集:  doc1: "kafka consumer timeout"   doc2: "consumer group rebalance"   doc3: "kafka broker isr"
正排（行式）:   doc1 ──▶ [kafka, consumer, timeout, …]      查询「kafka」→ 逐行扫
倒排（列式索引）:
  kafka     ──▶ [doc1, doc3]
  consumer  ──▶ [doc1, doc2]
  timeout   ──▶ [doc1]
  查询「kafka consumer」→ 倒排查两次 → 交/并集秒出结果；词项表按字典序排序存（term dictionary），
  再用 FST（有限状态转换器）压缩前缀实现 O(词长) 查找——这就是「为什么 ES 搜词快」
```

**写入链路**（近实时从哪来）：写请求到主分片 → 进内存 buffer + 写 **translog**（事务日志，默认每次请求 fsync，崩溃可回放）→ 每 `refresh_interval`（默认 1s）buffer 变成**不可变 segment** 并打开给搜索——**所以 ES 是近实时（秒级可见）**；buffer 攒满或 translog 到阈值触发 **flush**（清 translog、segment 落盘）；后台 **merge** 把零碎 segment 合并、真正物理删除被标记删除的文档。读懂这条链，3.10 的「最终一致 + 秒级可见」和「别拿 ES 当强一致主库」就都有了机制依据。副本一致性：写主分片成功后同步副本，`wait_for_active_shards` 控制要等几个副本确认（默认 1，即主分片即可）——**索引与副本的分片规划、节点角色属 ph19**，这里只需知道「ES 是分布式系统，写入有主从同步与 quorum 语义，读可能短暂读到旧数据」。

## 5. 使用场景

- **削峰填谷**：瞬时洪峰（秒杀下单、设备批量上报、日志高峰）直接打后端会打垮数据库——先入 MQ，消费者按自己的速度匀速处理。roadmap 示例链路 `业务服务 → Kafka → 消费服务 → Elasticsearch` 的 Kafka 承担的就是「缓冲 + 解耦」。秒杀的整体架构（限流、缓存、库存扣减）属 ph18，但「排队」这件事在 ph18 之前先由 MQ 兜住。
- **异步化与解耦**：订单创建后「发通知 + 减库存 + 积分 + 审计」一串动作若同步串调，下单接口被最慢的环节拖死——只发一条 `order.created` 事件，各消费者独立处理、独立扩缩容、坏了不影响主链路（ph16 的「链路拉直或异步事件化」在这里落地）。
- **Saga 补偿失败的异步重投（ph16 伏笔收口）**：ph16 ex06 的补偿动作若也失败，就投 MQ 重试 + 死信，由对账兜底——「补偿失败的重投/死信」正是本阶段 3.6 的内容。
- **本地消息表 / 事务消息（ph16 伏笔收口）**：ph16 3.4 的本地消息表「异步投递到 MQ」本阶段给两种落地：Kafka 事务 + Outbox（4.1）或 RocketMQ 事务消息（3.7）。
- **通用数据接入（ph21 铺垫）**：roadmap 第 21 节的 `数据源 → 接入服务 → Kafka → 清洗/告警/存储 → 运维后台` 与本阶段练习 2（设备数据消费）同构——上报量大、多消费者（实时监控/告警/历史存储各一组）、按设备 sn 分区保证单设备有序。
- **日志检索（本阶段项目形态）**：微服务（ph16）一多，排查问题要跨服务翻日志——典型链路是「应用 JSON 日志 → 采集 → Kafka → 清洗 → ES → 检索可视化」；采集 Agent 与 Kibana 告警的部署运维属 ph19，本阶段做的是 Kafka + ES 这一段（project 的设备事件搜索系统即其缩小版）。
- **消息积压：怎么发现、怎么处理**（roadmap 必会概念「消息积压需要监控」）：发现靠 lag（消费者落后生产者的偏移量，4.2 的命令可查），治理按原因分三路——消费变慢（单条处理耗时上去了：先看下游，再给消费者加并发/拆批）、生产暴涨（削峰失效：先看入口限流，属 ph18，再扩容消费者——**但消费者数不能超过分区数**，扩容前先加分区，加了分区旧分区数据要重分配，属 ph19 的集群操作）、消费者挂了（最紧急：修消费者比扩一切都有用）。积压的处理顺序口诀：**先救消费者，再谈扩容，最后才动分区**。
- **什么时候别用 MQ**：调用方能接受同步等待且链路短（直接用 ph16 的 HTTP 调用，省一套中间件运维）；需要强一致读（本地事务，ph15）；只有轻量通知（一个 topic 一个消费者，杀鸡用牛刀）。**引入 MQ = 引入三件新麻烦：重复消费要幂等、顺序要设计、积压要监控**——没这层觉悟不要上消息队列。
- **跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）：消息协议（Kafka wire protocol / AMQP / RocketMQ remoting）与 ES 的 REST 都是语言无关的，但**客户端体验分水岭在生态**——Java 的 spring-kafka 把「监听容器 + 重试 + 死信 + 序列化」都声明式化了（注解即消费者），Go 的 sarama/confluent 是薄客户端、重试与幂等要自己拼，Python 消费者常借用 Kafka 的 confluent-kafka 回调模型；而 ES 的 8.x Java client 与 REST 几乎是逐字对应，语言差异最小。横切点：**可靠性语义（至少一次/幂等）是协议层给的还是应用层拼的，决定了语言生态的样板量**——Java 靠框架把样板吃掉了。

选型速查（对照 3.1 对比表与 3.6 能力表）：

| 需求 | 首选 | 理由 |
|------|------|------|
| 日志/事件流、大数据管道、多消费者重放 | Kafka | 分区吞吐最高、保留期可配、生态最全 |
| 电商订单、强可靠 + 事务消息 + 延迟消息 | RocketMQ | 重试/死信/延迟/事务内建，国内运维经验多 |
| 路由复杂、中小流量、团队小 | RabbitMQ | Exchange 灵活、运维简单、AMQP 生态 |
| 全文检索 / 日志检索 / 站内搜索 | Elasticsearch | 倒排索引 + DSL + 聚合；别拿 MySQL 硬扛 |

## 6. 代码示例

> 完整可运行版在 [`examples/`](./examples/)（五个示例 + 一键 `docker compose` 起 Kafka/ES）。验证环境：OpenJDK 17 + Maven 3.9 + Spring Boot 3.3.0（spring-kafka 3.2.0 / kafka-clients 3.7.0 / ES 8.x Java client），命令统一 `mvn -o -Dmaven.repo.local=/tmp/m2clone test`（联网环境 `mvn test`）。**本环境未运行任何中间件**：依赖真 Kafka/ES 的代码（ex01/ex02/ex05/project/exercises）标注「未在本环境验证」；**两个纯 Java 示例 ex03/ex04 已在本机实测通过并标注「已验证」**。需要真 Kafka/ES 的示例必须先起服务（命令见 `examples/README.md`）。

```java
// examples/ex01-kafka-clients-basic/.../ConsumerMain.java —— 手动提交消费骨架（未在本环境验证）
props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);   // 关闭自动提交（3.3 的可靠消费前提）
consumer.subscribe(List.of("orders"));
while (running) {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(500));
    for (ConsumerRecord<String, String> record : records) {
        process(record);                                      // 处理（消费端必须幂等，3.4）
    }
    consumer.commitSync();                                    // 全批成功才提交 → at-least-once
}
```

```java
// examples/ex02-spring-kafka-idempotent-consume/.../OrderCreatedConsumer.java —— 幂等消费（未在本环境验证）
@KafkaListener(topics = "orders", groupId = "order-created-group")
public void onMessage(ConsumerRecord<String, String> record, Acknowledgment ack) {
    OrderEvent event = objectMapper.readValue(record.value(), OrderEvent.class);
    if (dedup.tryAcquire(event.orderId())) {                  // 去重表占位成功才处理
        orderService.markCreated(event);
    }
    ack.acknowledge();                                        // ack-mode=MANUAL
}
```

```java
// examples/ex04-inverted-index-demo/ex04-inverted-index-demo.java —— 手写倒排索引（纯 Java，已验证：OpenJDK 17 本机实测）
// 词项 → 文档 id 集合；查询 = 查表 + 集合交并；映射到 ES 的 term dictionary + postings（4.3）
Map<String, SortedSet<Integer>> postings = new HashMap<>();
for (Doc doc : docs) {
    for (String term : tokenize(doc.text())) {
        postings.computeIfAbsent(term, k -> new TreeSet<>()).add(doc.id());
    }
}
```

### 示例 1：Kafka 生产者/消费者骨架（[`examples/ex01-kafka-clients-basic/`](./examples/ex01-kafka-clients-basic/)）

kafka-clients 3.7.0 裸客户端：生产者（acks=all + 幂等 + 回调）、消费者（消费组 + 手动提交），订单 JSON 消息，需本地 Kafka（`docker compose up -d kafka`），未在本环境验证。

### 示例 2：可靠消费与幂等去重（[`examples/ex02-spring-kafka-idempotent-consume/`](./examples/ex02-spring-kafka-idempotent-consume/)）

spring-kafka 注解式消费：ack-mode=MANUAL + TTL 去重表 + 建单处理器；重复投递同一条消息只处理一次。需本地 Kafka，未在本环境验证。

### 示例 3：死信与延迟消息语义（[`examples/ex03-mq-dead-letter-delay-demo/ex03-mq-dead-letter-delay-demo.java`](./examples/ex03-mq-dead-letter-delay-demo/ex03-mq-dead-letter-delay-demo.java)）

纯 Java 单文件：虚拟时钟 + 延迟队列模拟「失败重试 → 死信」与「延迟消息到期投递」，无中间件依赖，`javac`/`java` 即可跑（已验证：OpenJDK 17 本机实测全部 PASS）。

### 示例 4：手写倒排索引（[`examples/ex04-inverted-index-demo/ex04-inverted-index-demo.java`](./examples/ex04-inverted-index-demo/ex04-inverted-index-demo.java)）

纯 Java 单文件：分词 → 建倒排 → term/match 查询与 AND/OR，演示「为什么倒排比 LIKE 快」，无中间件依赖（已验证：OpenJDK 17 本机实测全部 PASS）。

### 示例 5：ES 8.x 检索（[`examples/ex05-elasticsearch-java-client/`](./examples/ex05-elasticsearch-java-client/)）

ES 8.x Java client（elasticsearch-java）：建索引/映射 → 写文档 → match/bool/range 查询 → 反序列化。需本地 ES（`docker compose up -d elasticsearch`），未在本环境验证。

## 7. 总结

### 关键要点

- **MQ 三件套收益（削峰/解耦/异步）对应三件套代价（重复要幂等、顺序要设计、积压要监控）**——roadmap 必会概念第一条「消费者要设计幂等」是整个消息编程的第一性原理
- **可靠性分三段**：生产者 `acks=all + retries + 幂等`，broker 副本 `ISR/min.insync.replicas`，消费端**关自动提交、处理成功再提交**——任何「不丢」都落到 at-least-once，所以重复是常态、幂等是必须
- **顺序的默认姿势是分区顺序**：同 key 进同分区（key 别为 null、幂等开、单消费者线程），跨分区顺序不存在；被重平衡/重试打断后用业务 seq 丢弃迟到旧消息
- **死信与延迟没有免费午餐**：Kafka 无原生要自己拼（重试 topic + DLT），RocketMQ 原生（16 次重试 + %DLQ%、18 级延迟），RabbitMQ 靠路由模型（DLX/TTL/插件）
- **ES 快在倒排 + 分片并行**：text 分词全文检索、keyword 精确匹配别配反；查询用 bool 组合；写入近实时（~1s）——**ES 是最终一致的查询视图，主库永远是 MySQL，同步用 MQ + 对账兜底**
- **本阶段是 ph16 伏笔的收口**：本地消息表 → 事务消息/Outbox、补偿失败 → 重试/死信、削峰解耦 → 生产消费链路；也是 ph18 的前置——削峰已由 MQ 扛住，缓存与限流是下一层防护

### 阶段验收清单

- [ ] 能对比 Kafka / RocketMQ / RabbitMQ 的模型与定位，给一个场景说出选型理由
- [ ] 能解释消息可靠性的三个环节与 at-least-once / at-most-once / exactly-once 语义，说出为什么重复不可避免
- [ ] 能写出带手动提交的消费者，并为它设计幂等去重（去重表 + 数据库唯一约束 + 状态机）
- [ ] 能解释分区顺序与全局顺序的取舍，说出 key 路由与重试对顺序的影响
- [ ] 能说清死信队列与延迟消息在三款 MQ 里的实现差异（DLT / %DLQ% / DLX、18 级延迟 / TTL+DLX）
- [ ] 能说出 Kafka 的 ISR/AR/高水位的含义，acks=all 与 min.insync.replicas 的关系，rebalance 为什么拖停全组
- [ ] 能解释倒排索引原理与 text/keyword、match/term/bool 的查询差异
- [ ] 能设计「业务 → MQ → 消费 → ES」的索引同步链路，说出为什么 ES 是最终一致的查询视图

### 跨语言对比

- Java 消费 Kafka 的体验是「框架吃掉样板」：spring-kafka 一个注解 + 一个配置文件就完成了监听容器/序列化/手动 ack/重试/死信；Go/Python 的客户端更薄，可靠性语义要显式拼装。消息协议与 ES REST 语言无关，差异全在生态层（为 analysis/ 与 Tenet 合成积累素材）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：异步订单处理（练习 1）→ 设备数据消费（练习 2）→ 告警消息推送（练习 3）→ 日志搜索（练习 4），四题对应 roadmap 第 17 节列出的四个练习。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**设备事件搜索系统**（roadmap 推荐项目）——落地 roadmap 示例链路「业务服务 → Kafka → 消费服务 → Elasticsearch」：模拟设备发事件 → Kafka（按 sn 分区保证单设备有序）→ 消费服务幂等消费 → ES 索引 + 检索 API；无中间件环境下可用内存引擎 + 直接注入接口跑通检索语义（两档引擎可切换，见 project README）。建议完成练习后再动手。
- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（完整链路需 docker compose 起 Kafka + ES）

### 下一阶段

[ph18 缓存与高并发阶段](../ph18-cache-concurrency/18-cache-concurrency.md)——本阶段用 MQ 削峰解耦、用 ES 扛检索，下一层防护是缓存与限流：Redis/Caffeine 缓存穿透/击穿/雪崩、分布式锁与限流、秒杀架构、连接池与批量优化。本阶段埋的前置：消息队列只是把「瞬时洪峰」摊平成「匀速消费」，消费端背后的数据库与搜索仍可能被打穿——ph18 的缓存分层（本地缓存 → Redis → 数据库）就是消费链路的下一道防线；roadmap 第 21 节的设备数据实时缓存也建立在本阶段设备数据消费练习之上。
