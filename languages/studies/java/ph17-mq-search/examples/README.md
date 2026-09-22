# ph17 消息队列与搜索 示例

> 五个示例对应主文档「3. 语法与参数」的主线：Kafka 客户端骨架（ex01）→ spring-kafka 可靠消费与幂等去重（ex02）→ 死信/延迟消息语义（ex03，纯 Java）→ 倒排索引原理（ex04，纯 Java）→ ES 8.x Java client 检索（ex05）。验证环境：**OpenJDK 17 + Maven 3.9 + Spring Boot 3.3.0**（依赖管理基线，与 ph15/ph16 同源；spring-kafka 3.2.0 / kafka-clients 3.7.0 / co.elastic.clients:elasticsearch-java 8.13.4）。

## 验证状态（重要，如实标注）

**本环境未运行 Kafka/ES 中间件、未执行 Maven 构建**：ex01/ex02/ex05 需要本地 Kafka/ES 服务（本目录 `docker-compose.yml` 一键起），依赖真中间件的代码标注「未在本环境验证」；**ex03/ex04 是纯 Java 单文件，已在本机实测通过并标注「已验证」**（`javac`/`java` 即可，无中间件依赖）——请在起好中间件的机器上按命令实测依赖 Kafka/ES 的示例，不要假设本仓库已替你跑过。

依赖可用性（仅按本机离线仓库目录 `ls` 复核，非构建验证）：`kafka-clients 3.7.0`、`spring-kafka 3.2.0` 目录在 `/tmp/m2clone` 可见；ES 8.x 的 `elasticsearch-java` 不在离线缓存，需联网环境首次 `mvn test` 拉取。命令统一支持离线模式 `mvn -o -Dmaven.repo.local=/tmp/m2clone …`（依赖缺失时先联网 `mvn …` 拉一次），联网环境直接 `mvn …`。

## 中间件启动（需要真 Kafka/ES 的示例先跑这一步）

```bash
# 1. 起 Kafka（KRaft 单节点，9092）与 Elasticsearch（8.x 单节点，9200，关安全）
docker compose up -d
# 2. 等待就绪：Kafka 可用 kafka-topics.sh 或直接跑示例（auto.create.topics 默认开）；
#    ES 就绪检查（约等 20~60 秒）
curl -s http://localhost:9200/ | head
# 3. 结束清理
docker compose down
```

> docker compose 文件与 project/ 的相同（Kafka + ES 两服务），本目录这份服务于 examples 五个示例；RocketMQ/RabbitMQ 的本地服务本阶段不跑（机制与代码片段见主文档 3.6/3.7，未在本环境验证）。

## 示例列表

| 目录/文件 | 主题 | 依赖 | 运行命令 | 验证状态 |
|------|------|------|---------|---------|
| ex01-kafka-clients-basic/ | Kafka 生产者/消费者骨架：acks=all + 幂等 + 回调、消费组 + 手动提交 | kafka-clients 3.7.0 + jackson | 先 `docker compose up -d kafka`，再 `mvn -o -Dmaven.repo.local=/tmp/m2clone spring-boot:run -Dspring-boot.run.main-class=com.example.ex01.ProducerMain`（消费端换 `ConsumerMain`） | 未在本环境验证 |
| ex02-spring-kafka-idempotent-consume/ | spring-kafka 注解式可靠消费：ack-mode=MANUAL + TTL 去重表，重复投递只处理一次 | spring-kafka 3.2.0（Boot 管理）+ jackson | 先起 kafka，再 `mvn -o -Dmaven.repo.local=/tmp/m2clone spring-boot:run -Dspring-boot.run.main-class=com.example.ex02.Ex02Application`，另开终端用 ex01 的 ProducerMain 连发消息 | 未在本环境验证 |
| ex03-mq-dead-letter-delay-demo/ex03-mq-dead-letter-delay-demo.java | 死信 + 延迟消息语义：失败重试→死信、到期才投递（虚拟时钟，结果确定） | 无（纯 Java 17） | `javac ex03-mq-dead-letter-delay-demo.java && java DeadLetterDelayDemo` | 已验证（OpenJDK 17.0.18 本机实测 PASS） |
| ex04-inverted-index-demo/ex04-inverted-index-demo.java | 手写倒排索引：分词→词项→文档集，term/match 查询、AND/OR | 无（纯 Java 17） | `javac ex04-inverted-index-demo.java && java InvertedIndexDemo` | 已验证（OpenJDK 17.0.18 本机实测 PASS） |
| ex05-elasticsearch-java-client/ | ES 8.x 检索：建索引/映射→写文档→match/bool/range 查询 | elasticsearch-java 8.13.4 | 先 `docker compose up -d elasticsearch`，再 `mvn -o -Dmaven.repo.local=/tmp/m2clone spring-boot:run -Dspring-boot.run.main-class=com.example.ex05.EsSearchDemo` | 未在本环境验证 |

## 示例速览与教学点

### ex01：Kafka 生产者/消费者骨架（未在本环境验证）

- 生产者：`acks=all`（等 ISR 全员确认）+ `enable.idempotence=true`（幂等，3.x 默认）+ `retries` 大值 + send 回调观察 `partition/offset`——一条消息写了哪个分区、排到第几位一目了然
- 消费者：消费组 `ex01-order-group`、`enable.auto.commit=false`、全批处理完 `commitSync`（at-least-once）；按 key=orderId 分区路由，观察「同 key 的消息总在同一个分区」
- 体验：连发两次 ProducerMain 后重启 ConsumerMain，配合 `auto.offset.reset=earliest` 能看到重复消费的起点语义

### ex02：spring-kafka 可靠消费 + 幂等去重（未在本环境验证）

- `@KafkaListener` + `application.yml` 的 `spring.kafka.listener.ack-mode: manual`，监听方法收到 `Acknowledgment` 自己提交
- `DedupStore`（TTL 去重表）占位成功才处理，重复投递同一条 `orderId` 只建单一次（日志里 `created` 计数只 +1）——对应主文档 3.4「为什么重复不可避免 + 去重表方案」
- 把 ex01 的 ProducerMain 连续跑两遍（同 key 的消息被重复投递），观察去重效果

### ex03：死信与延迟消息语义（纯 Java，已验证）

- 虚拟时钟驱动，无真实时间依赖：消息带 `availableAt`，broker 只投「已到期」的消息——延迟消息 = 把 `availableAt` 设到未来
- 场景一「失败重试→死信」：处理恒失败，attempt 达到上限进 DLQ（对应 Kafka `.dlt` / RocketMQ `%DLQ%` / RabbitMQ DLX）
- 场景二「延迟投递」：两条消息先后入队、后一条到期时间更晚，断言投递顺序按到期时间而非入队顺序

### ex04：手写倒排索引（纯 Java，已验证）

- 小写化 + 按非字母数字切分的简易分词（对比 ES 的 standard 分析器），建「词项 → 文档 id 集合」倒排表
- `searchTerm`（term 查询）、`searchAny`（OR）、`searchAll`（AND）与相关性计数排序——直观回答「为什么倒排检索不用扫全表」
- 刻意保留一个教学缺口：**简易分词切不了中文**（对照主文档 3.8 的中文分词注）

### ex05：ES 8.x Java client 检索（未在本环境验证）

- 官方客户端 `elasticsearch-java`：`RestClientTransport + JacksonJsonpMapper` 封装；建索引（text/keyword/date 映射）→ 写 3 条日志文档 → match/term/bool+range 查询 → 反序列化回 record
- 与主文档 3.9 的 REST DSL 逐字段对照，理解「Java client 是 DSL 的类型安全版」
- 换 ES 前先删旧索引重建（幂等脚本），避免 mapping 冲突

## 端口与清理

Kafka `9092`、ES `9200`；示例无固定应用端口（非 Web）。`docker compose down` 停止并删除容器；中途异常残留用 `docker ps -a | grep mqs-` 检查后 `docker rm -f` 清理。
