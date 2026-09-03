# ph17 阶段项目：设备事件搜索系统

## 需求

roadmap「17. 消息队列与搜索阶段」推荐项目之二——**设备事件搜索系统**，把 roadmap 示例链路「业务服务 → Kafka → 消费服务 → Elasticsearch」完整落一遍（本仓库 ph16 的「设备管理服务」练习升级版：设备产生的不仅是注册请求，而是持续的事件流）：

**模拟设备发事件 → Kafka（`device-events`，按设备 sn 分区，单车/单设备有序）→ 消费服务（group 内手动 ack + (sn,seq) 幂等去重）→ 双引擎索引（内存引擎开箱可跑 / ES 引擎走真实检索）→ REST 检索 API（关键词 + 过滤 + 时间窗）**。

数据纪律延续本仓库各阶段：消费端**幂等**（roadmap 必会概念「消费者要设计幂等」）、**分区影响顺序和吞吐**（按 sn 分区保序 + 可并行）、**索引同步一致性**（消费成功才 ack，写索引失败走重试——本骨架先「失败即记日志不 ack 交给容器重试」的简化策略，重试/死信的完整版见 exercises 练习 3）。设备事件模型沿用 ph16 车联网语境：`sn`（设备号）/`seq`（设备侧序号）/`type`（alarm / heartbeat / location）/`severity`/`message`/`ts`。

> 本阶段只做「事件 → MQ → 消费 → 检索」这段；**设备的接入鉴权/协议层属 ph21 车联网方向**，**采集与部署监控属 ph19**，**ES 分片规划属 ph19**——本项目用单节点 docker 演示，不越界。

## 技术栈与验证环境

- OpenJDK 17 + Maven 3.9 + Spring Boot 3.3.0（依赖管理基线）+ kafka-clients 3.7.0（device-emitter）+ spring-kafka 3.2.0 / elasticsearch-java 8.13.4（search-service）
- 模块：`device-emitter`（无 Spring，纯 main 的模拟设备）→ `search-service`（Spring Boot：Kafka 消费 + 双引擎索引 + REST 检索），父 pom 聚合两个模块
- **双引擎设计（本项目的可复现关键）**：`EventIndexer` 接口有两个实现——`InMemoryEventIndexer`（内存倒排，参考 examples/ex04，**无中间件可跑**）与 `EsEventIndexer`（真实 ES 8.x client）。`app.search.engine=memory|es` 切换（默认 `memory`）：没有 Kafka/ES 也能把「事件 → 索引 → 检索」的完整语义跑通；有 docker 则切 `es` 并跑完整链路
- **全部未在本环境验证**：命令按代码与官方文档口径编写，请按下方步骤实测

## 运行步骤（三种模式，按本机条件选）

### 模式 A：纯检索演示（无中间件，最快）

```bash
# 1. 构建（联网环境去掉 -o 参数；elasticsearch-java 不在本机离线缓存，联网首次拉取）
mvn -o -Dmaven.repo.local=/tmp/m2clone -DskipTests package
# 2. 起 search-service（默认 engine=memory，不连 Kafka/ES 也能启动；Kafka 连不上只影响消费线程）
mvn -o -Dmaven.repo.local=/tmp/m2clone -pl search-service spring-boot:run \
  -Dspring-boot.run.main-class=com.example.device.search.SearchServiceApplication
# 3. 直接注入事件（绕过 MQ——无 Kafka 时验证索引与检索用），再检索：
curl -s -X POST localhost:18080/api/events -H 'Content-Type: application/json' \
  -d '{"sn":"EV-001","seq":1,"type":"alarm","severity":"HIGH","message":"battery low","ts":1700000000000}'
curl -s 'localhost:18080/api/events/search?q=battery'
```

### 模式 B：完整链路（docker compose 起 Kafka + ES）

```bash
# 1. 起中间件（Kafka KRaft 单节点 9092 + ES 8.x 单节点 9200，见 docker-compose.yml）
docker compose up -d
curl -s http://localhost:9200/ | head          # 等 ES 就绪（约 20~60 秒）
# 2. 以 ES 引擎起 search-service：
mvn -o -Dmaven.repo.local=/tmp/m2clone -pl search-service spring-boot:run \
  -Dspring-boot.run.main-class=com.example.device.search.SearchServiceApplication \
  -Dspring-boot.run.arguments=--app.search.engine=es
# 3. 跑模拟设备（往 device-events 发 100 条事件，key=sn）：
mvn -o -Dmaven.repo.local=/tmp/m2clone -pl device-emitter exec:java \
  -Dexec.mainClass=com.example.device.emitter.DeviceEmitter -Dexec.args="100"
# 4. 检索（消费端已把事件写入 ES）：
curl -s 'localhost:18080/api/events/search?q=alarm'
curl -s 'localhost:18080/api/events/search?type=alarm&severity=HIGH'
curl -s 'localhost:18080/api/events/count'
# 5. 结束清理
docker compose down
```

> 模式 B 的 device-emitter 用了 `exec:java`（exec-maven-plugin 需联网或离线缓存有该插件，未在本环境验证）；若插件缺失，也可复制 examples/ex01 的 ProducerMain 改造（把 topic 换成 `device-events`、key 换成 sn）——语义相同。

## 功能清单

- [x] **device-emitter（模拟设备）**：按 `sn-001..sn-010` 循环生成事件（type 轮换 alarm/heartbeat/location、severity 随机、seq 每台自增），key=sn 发往 `device-events`（保证单车有序），可配条数与速率
- [x] **Kafka 消费**：`@KafkaListener` group `device-search-group`、ack-mode=manual；**(sn,seq) 幂等去重**（重复投递只索引一次）+ seq 回退丢弃（迟到旧数据）
- [x] **双引擎索引**：`EventIndexer` 接口——memory（内存 Map + 简易倒排，无中间件）与 es（真实索引 `device-events`：message text / type、severity、sn keyword / ts date）
- [x] **REST 检索**：`GET /api/events/{eventId}`（内存按 id）、`GET /api/events/search?q=&type=&severity=`（引擎查询，两引擎行为对齐）、`GET /api/events/count`（按 severity 分组统计：memory 遍历 / es terms 聚合）
- [x] **直接注入端点**：`POST /api/events`（内存引擎造数，绕过 MQ，供模式 A 自测；真实链路的事件入口是 Kafka）
- [x] **离线可测的单元测试**：内存引擎检索语义与 (sn,seq) 去重（`mvn -o ... test` 跑，无需中间件）

## 验收标准

- **无中间件验收（模式 A）**：`mvn -o -Dmaven.repo.local=/tmp/m2clone test`（search-service 的 InMemoryEventIndexerTest / DeviceEventDedupTest 全绿，未在本环境验证）；注入 3 条不同 severity 事件后 `search?q=`、`count` 结果与手算一致
- **完整链路验收（模式 B，未在本环境验证）**：emitter 发 100 条 → 消费端日志出现 `indexed sn=... seq=...` → `search?q=alarm` 返回 type=alarm 的事件、`count` 的 severity 分布与生成参数对得上；重复投递同一事件（emitter 连发两遍同 seq）只索引一次
- **能画出链路并说出每跳职责**：device-emitter（生产者：acks=all + key=sn）→ Kafka（分区内有序、组内并行）→ search-service 消费（手动 ack + 幂等）→ EventIndexer（memory/es 两档）→ 检索 API；并说明与真实生产形态的差距（见「扩展方向」）
- **能回答三个「为什么」**：为什么消费端要 (sn,seq) 幂等（at-least-once，主文档 3.4）；为什么 key=sn 分区（顺序 + 并行，3.5）；为什么 ES 是最终一致的查询视图（索引消费有延迟，主库/事实源在事件源头，3.10）

## 扩展方向

- **重试与死信**：消费「索引失败」目前是简化策略（记日志后不 ack 交给容器重试）；把 exercises 练习 3 的重试处理器接进来：失败退避重试 → 超限投 `device-events.dlt` → 对账任务人工处理（主文档 3.6）
- **真实集群**：单节点 docker 换成多 broker Kafka 与多节点 ES——分区/副本规划、索引分片与生命周期策略属 ph19 DevOps 与部署阶段
- **状态外置**：(sn,seq) 去重表在单实例内存；多实例部署时换 Redis SETNX + 数据库唯一约束（主文档 3.4 方案表；Redis 用法 ph16 已备）
- **检索增强**：type/severity/sn 的过滤改 filter 语义不算分、message 加 ik 中文分词、时间直方图聚合（主文档 3.9/3.10；中文分词插件与分片规划超出本阶段）
- **接入真实设备**：模拟 emitter 换成车机上报网关（鉴权/协议/限流），衔接 roadmap 第 21 节车联网方向；告警事件在此触发（本阶段练习 3 的主题）

## 附录：模块与端口

- search-service 默认端口 `18080`（`application.yml` 的 `server.port`；测试全部用 `--server.port=0` 随机端口）
- topic：`device-events`（自动创建；生产环境建 topic 时指定分区数与副本因子，属 ph19 DevOps 与部署阶段）
- 父 pom 聚合 `device-emitter` 与 `search-service`，构建命令在 `project/` 根目录执行
