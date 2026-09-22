// examples/ex02-fake-source-ingest/MetricFrame.java —— 解析后的指标帧(不可变 record)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
record MetricFrame(String sourceId, long seq, double cpuPct, double latencyMs, double diskTempC) {
    /** 生产链路常把帧的文本/字节形态与业务形态分开：本 record 是后者。 */
    static MetricFrame of(String sourceId, long seq, double soc, double latencyMs, double temp) {
        return new MetricFrame(sourceId, seq, soc, latencyMs, temp);
    }
}
