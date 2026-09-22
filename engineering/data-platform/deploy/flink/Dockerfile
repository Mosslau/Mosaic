# OceanVerse Flink 运行镜像（第 1 阶段第 3 步：实时作业）
#
# 为什么必须自建（实测, 不是照抄文档）:
#   官方 `flink:1.20.5-scala_2.12-java17` 的 /opt/flink/lib **不含任何连接器** ——
#   实测只有 flink-dist / table / json / csv / cep / log4j。Kafka 源与 ClickHouse 汇都得自己补。
#
# 为什么在这里把版本钉死:
#   连接器的版本号与 Flink **minor** 强绑定（本例 3.4.0-**1.20** ↔ Flink 1.20.x）。
#   错配的症状不是构建失败，而是**作业提交时才炸**（NoSuchMethodError / ClassNotFoundException），
#   排查成本远高于在这里钉一次。故三个 jar 的版本都作为 ARG 显式写出，并打印到构建日志。
#
# 三个 jar:
#   flink-sql-connector-kafka     —— Kafka source + 结果 topic sink
#   flink-metrics-prometheus      —— 让 JM/TM 暴露 /metrics(Prometheus 抓取) —— **镜像不自带**(实测 opt/ 里没有),
#                                    没有它 Flink 就是"黑盒": 作业静默死掉无人知 —— Kafka source + **结果 topic 的 sink**(shaded 版本,
#   勿换成 flink-connector-kafka)。
#
# **走过的弯路(留档, 免得下次再试)**: 本镜像曾试图补 ClickHouse sink 连接器, 三条路全断 ——
#   ① flink-connector-jdbc 3.4.0 + clickhouse-jdbc: Flink 报
#      `Could not find any jdbc factory that can handle url 'jdbc:clickhouse:...'`,
#      并把可用工厂全列了出来(CrateDB/Db2/Derby/MySQL/OceanBase/Oracle/PostgreSQL/SqlServer/Trino)
#      —— 该连接器**没有 ClickHouse dialect**;
#   ② ClickHouse 官方 `com.clickhouse.flink:flink-connector-clickhouse-1.17`: 内省其 -all jar
#      (0.2.0 与 0.1.3)只有 `org/apache/flink/connector/clickhouse/sink/*` 与 ClickHouse client 类,
#      **没有任何 Table/SQL 工厂类、也没有 Flink SPI 文件** → 它是 DataStream API 专用,
#      SQL DDL 里 `connector='clickhouse'` 永远找不到工厂(注意: CREATE TABLE 是惰性的, 不报错,
#      只有真正 INSERT 时才失败 —— 早先一次"探针成功"就是这么被骗的);
#   ③ Maven Central 上其余 "clickhouse flink" 构件均为 StreamX / StreamPark 等框架专用。
#   结论: **Flink SQL 写结果 topic → ClickHouse Kafka 引擎表 + 物化视图落库**(见 realtime/)。
#
# 为什么不落 S3/MinIO 插件: 镜像 /opt/flink/opt/ 已自带 flink-s3-fs-hadoop-1.20.5.jar，
#   需要时用官方入口的 ENABLE_BUILT_IN_PLUGINS 启用即可，**无需下载**（见 deploy/docker-compose.yaml）。
#
# 为什么要在这里建 checkpoint/savepoint 目录:
#   容器默认用户是 `flink`(uid 9999)。命名卷首次挂载时由 Docker 按**镜像内该路径的属主**初始化 ——
#   路径不存在就建成 root:root，于是 Flink 写 checkpoint 时报 Permission denied（症状是作业一直
#   "等待首个 checkpoint"、UI 上 checkpoint 全线失败）。在这里建好并 chown 即可根治。
#
# 构建（仓库根执行）:
#   docker build -f deploy/flink/Dockerfile -t oceanverse/flink:1.20.5 deploy/flink
#   可用 --build-arg MAVEN_MIRRORS="<源1> <源2>" 覆盖（空格分隔，按序 failover）
#
# 为什么要多源 failover（实测）:
#   宿主机能连 repo1.maven.org，但**构建容器里第一次拉取报 curl exit 35（TLS 连接失败）**；
#   随后在容器内逐个探测又都能连（repo1 1.4s / aliyun 0.17s / huawei 0.15s）。
#   即：这是**瞬时抖动**而非网络不可达 —— 单一源会让构建随机失败，故按序重试多个源。
FROM flink:1.20.5-scala_2.12-java17

ARG MAVEN_MIRRORS="https://repo1.maven.org/maven2 https://maven.aliyun.com/repository/public https://mirrors.huaweicloud.com/repository/maven"
ARG KAFKA_CONNECTOR_VERSION=3.4.0-1.20
ARG FLINK_VERSION=1.20.5
# ClickHouse 官方 Flink 连接器: 只有 -1.17 / -2.0.0 两个构建, **没有 1.20**
# (实测: flink-connector-jdbc 3.4.0 的工厂列表里没有 ClickHouse,
#  故 JDBC 路线走不通)。这里用 1.17 构建跑在 1.20 上 -- 同大版本内的兼容性实测通过后才保留。

USER root
RUN set -eux; \
    fetch() { \
      path="$1"; out="$2"; \
      for m in $MAVEN_MIRRORS; do \
        if curl -fsSL --retry 3 --retry-delay 2 --connect-timeout 15 -o "/opt/flink/lib/$out" "$m/$path"; then \
          echo "  ok   $out  <- $m"; return 0; \
        fi; \
        echo "  miss $out  <- $m（换下一个源）"; \
      done; \
      echo "  FAIL $out：所有源都不可达"; return 1; \
    }; \
    fetch "org/apache/flink/flink-sql-connector-kafka/${KAFKA_CONNECTOR_VERSION}/flink-sql-connector-kafka-${KAFKA_CONNECTOR_VERSION}.jar" \
          "flink-sql-connector-kafka-${KAFKA_CONNECTOR_VERSION}.jar"; \
    fetch "org/apache/flink/flink-metrics-prometheus/${FLINK_VERSION}/flink-metrics-prometheus-${FLINK_VERSION}.jar" \
          "flink-metrics-prometheus-${FLINK_VERSION}.jar"; \
    echo "--- lib 里的连接器与 reporter（构建日志留痕，便于日后核对版本漂移）---"; \
    ls -l /opt/flink/lib | grep -E 'connector|clickhouse|metrics-prometheus'; \
    mkdir -p /opt/flink/checkpoints /opt/flink/savepoints; \
    chown -R flink:flink /opt/flink/checkpoints /opt/flink/savepoints; \
    ls -ld /opt/flink/checkpoints /opt/flink/savepoints
USER flink
