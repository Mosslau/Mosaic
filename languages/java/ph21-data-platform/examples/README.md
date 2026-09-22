# ph21 数据平台 / 数据中心后端 Java 示例

> 九个示例对应主文档「3. 语法与参数」主线：节点管理聚合状态机(ex01)→ 按 sourceId 分片的高吞吐接入(ex02)→ CHM 实时状态缓存(ex03)→ SPI 告警规则引擎(ex04)→ Kafka 指标消费语义(ex05)→ 发布批次状态机/回滚(ex06)→ 作业历史查询(ex07)→ 运维后台聚合(ex08)→ Netty 长连接网关(ex09)。验证环境：**OpenJDK 17.0.18(Homebrew)**。

## 验证状态(如实标注)

| 目录 | 主题 | 依赖 | 验证状态 |
|------|------|------|---------|
| ex01-node-management/ | 节点生命周期聚合 + 状态机 + 审计事件流 | 无(纯 Java 17) | **已验证**：4/4 PASS |
| ex02-fake-source-ingest/ | 按 sourceId 哈希分片的有界队列接入层(背压/去重/坏帧拒绝) | 无 | **已验证**：6/6 PASS(运行 3 次稳定) |
| ex03-source-state-cache/ | ConcurrentHashMap 实时状态缓存(compute 原子读改写 + 乱序丢弃) | 无 | **已验证**：4/4 PASS(丢弃计数 8000 > 0) |
| ex04-alert-rule-engine/ | ServiceLoader SPI 装载规则 + 动态代理计时 | 无(classpath 需带 spi-resources) | **已验证**：4/4 PASS(SPI 发现 2 规则) |
| ex05-metric-consumer/ | 内存版 Kafka 语义：offset/poll/幂等去重/重放 | 无(真 Kafka 见下方说明) | **已验证**：3/3 PASS |
| ex06-release-batch/ | 发布批次单节点状态机 + 整体回滚 + 审计轨迹 | 无 | **已验证**：6/6 PASS |
| ex07-job-history/ | 作业历史分桶存储 + 时间窗/最新点查询(ConcurrentSkipListMap) | 无 | **已验证**：4/4 PASS |
| ex08-ops-console/ | 运维后台跨域聚合视图(事件流 → 运营快照) | 无 | **已验证**：5/5 PASS |
| ex09-netty-gateway/ | Netty 长连接网关(主从 Reactor + line codec + 在线表) | netty-all 4.1.49.Final(本机 jar) | **已验证**：6/6 PASS(本机实测) |

> ex05 的 **真 Kafka 形态未在本环境验证**：本机无 broker。语义由内存版复刻(分区日志/offset/幂等/重放)，需真件时：
> ```bash
> docker run -d --name kafka-demo -p 9092:9092 apache/kafka:3.7.0
> # 生产消费者需引入 kafka-clients 依赖(如 mvn: org.apache.kafka:kafka-clients:3.7.0)，
> # 接入代码骨架见主文档 3.3 节代码块(标「未验证」)。
> ```

## 一条验证主链(纯 Java 示例，从零开始)

```bash
# 1. 编译全部到 /tmp(先进入各示例目录再 javac；产物不落仓库)
JAVAC=/opt/homebrew/opt/openjdk@17/bin/javac
JAVA=/opt/homebrew/opt/openjdk@17/bin/java
OUT=/tmp/tl21-cls && mkdir -p $OUT

# ex01：节点管理(聚合状态机)
cd ex01-node-management && $JAVAC -encoding UTF-8 -d $OUT *.java && $JAVA -cp $OUT NodeManagementDemo && cd ..

# ex02：接入层分片/背压
cd ex02-fake-source-ingest && $JAVAC -encoding UTF-8 -d $OUT *.java && $JAVA -cp $OUT IngestDemo && cd ..

# ex03：状态缓存
cd ex03-source-state-cache && $JAVAC -encoding UTF-8 -d $OUT *.java && $JAVA -cp $OUT StateCacheDemo && cd ..

# ex04：规则引擎(classpath 需带 spi-resources)
cd ex04-alert-rule-engine && $JAVAC -encoding UTF-8 -d $OUT *.java && $JAVA -cp $OUT:spi-resources AlertEngineDemo && cd ..

# ex05：指标消费语义
cd ex05-metric-consumer && $JAVAC -encoding UTF-8 -d $OUT *.java && $JAVA -cp $OUT ConsumerDemo && cd ..

# ex06：发布批次
cd ex06-release-batch && $JAVAC -encoding UTF-8 -d $OUT *.java && $JAVA -cp $OUT ReleaseDemo && cd ..

# ex07：作业历史查询
cd ex07-job-history && $JAVAC -encoding UTF-8 -d $OUT *.java && $JAVA -cp $OUT JobHistoryQueryDemo && cd ..

# ex08：运维后台
cd ex08-ops-console && $JAVAC -encoding UTF-8 -d $OUT *.java && $JAVA -cp $OUT OpsConsoleDemo && cd ..
```

## Netty 网关示例(ex09)

```bash
# ex09 需要 netty-all 4.1.49.Final jar。本机用 ~/.m2/repository.bak 下现成 jar 实测；
# 无该 jar 时从 Maven Central 获取：https://repo1.maven.org/maven2/io/netty/netty-all/4.1.49.Final/netty-all-4.1.49.Final.jar
NETTY=/path/to/netty-all-4.1.49.Final.jar
cd ex09-netty-gateway
$JAVAC -encoding UTF-8 -cp $NETTY -d $OUT *.java
$JAVA -cp "$NETTY:$OUT" GatewayDemo        # 期望 6/6 PASS
```

## 与 exercises/project 的关系

- 练习 1(数据源数据上报 API)= ex02 的上报面加约束(去重/量程/统计)，参考 `sol-01`
- 练习 2(节点管理系统)= ex01 加批量管理操作(节点集群注册/批量查在线)，参考 `sol-02`
- 练习 3(版本发布 升级平台)= ex06 的完整版(版本仓库 + 批次编排 + 进度查询)，参考 `sol-03`
- 练习 4(Kafka 指标消费服务)= ex05 加多消费组与积压监控，参考 `sol-04`

## 清理

所有编译产物输出到 `/tmp`，仓库目录不落 `.class`。清理：`rm -rf /tmp/tl21-cls /tmp/tl21-ex`。
