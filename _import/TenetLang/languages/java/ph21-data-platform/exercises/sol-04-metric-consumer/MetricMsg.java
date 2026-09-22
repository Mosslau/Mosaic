// exercises/sol-04-metrics-consumer/MetricMsg.java —— 指标消息(record，分区键 = SOURCE_ID)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-sol *.java
record MetricMsg(String sourceId, long seq, double cpuPct) {
    /** 幂等键：同g同 seq 全平台只处理一次。 */
    String idempotencyKey() { return sourceId + "#" + seq; }
}
