# OceanVerse Flink 运行镜像（第 1 阶段第 3 步：实时作业）
#
# 为什么必须自建（2026-09-20 实测，不是照抄文档）:
#   官方 `flink:1.20.5-scala_2.12-java17` 的 /opt/flink/lib **不含任何连接器** ——
#   实测只有 flink-dist / table / json / csv / cep / log4j。Kafka 源与 ClickHouse 汇都得自己补。
#
# 为什么在这里把版本钉死:
#   连接器的版本号与 Flink **minor** 强绑定（本例 3.4.0-**1.20** ↔ Flink 1.20.x）。
#   错配的症状不是构建失败，而是**作业提交时才炸**（NoSuchMethodError / ClassNotFoundException），
#   排查成本远高于在这里钉一次。故三个 jar 的版本都作为 ARG 显式写出，并打印到构建日志。
#
# 三个 jar 各自的作用:
#   flink-sql-connector-kafka —— Kafka source（SQL 侧，shaded 版本，勿换成 flink-connector-kafka）
#   flink-connector-jdbc      —— JDBC sink（Flink 无官方 ClickHouse 连接器，走 JDBC 落表）
#   clickhouse-jdbc (-all)    —— ClickHouse JDBC 驱动（-all 自带依赖，避免再补一堆传递 jar）
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
# 为什么要多源 failover（2026-09-20 实测）:
#   宿主机能连 repo1.maven.org，但**构建容器里第一次拉取报 curl exit 35（TLS 连接失败）**；
#   随后在容器内逐个探测又都能连（repo1 1.4s / aliyun 0.17s / huawei 0.15s）。
#   即：这是**瞬时抖动**而非网络不可达 —— 单一源会让构建随机失败，故按序重试多个源。
FROM flink:1.20.5-scala_2.12-java17

ARG MAVEN_MIRRORS="https://repo1.maven.org/maven2 https://maven.aliyun.com/repository/public https://mirrors.huaweicloud.com/repository/maven"
ARG KAFKA_CONNECTOR_VERSION=3.4.0-1.20
ARG JDBC_CONNECTOR_VERSION=3.4.0-1.20
ARG CLICKHOUSE_JDBC_VERSION=0.8.6

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
    fetch "org/apache/flink/flink-connector-jdbc/${JDBC_CONNECTOR_VERSION}/flink-connector-jdbc-${JDBC_CONNECTOR_VERSION}.jar" \
          "flink-connector-jdbc-${JDBC_CONNECTOR_VERSION}.jar"; \
    fetch "com/clickhouse/clickhouse-jdbc/${CLICKHOUSE_JDBC_VERSION}/clickhouse-jdbc-${CLICKHOUSE_JDBC_VERSION}-all.jar" \
          "clickhouse-jdbc-${CLICKHOUSE_JDBC_VERSION}-all.jar"; \
    echo "--- lib 里的连接器（构建日志留痕，便于日后核对版本漂移）---"; \
    ls -l /opt/flink/lib | grep -E 'connector|clickhouse'; \
    mkdir -p /opt/flink/checkpoints /opt/flink/savepoints; \
    chown -R flink:flink /opt/flink/checkpoints /opt/flink/savepoints; \
    ls -ld /opt/flink/checkpoints /opt/flink/savepoints
USER flink
