// examples/ex03-source-state-cache/SourceState.java —— 数据源实时状态快照(不可变 record)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
record SourceState(String sourceId, long seq, double cpuPct, long updatedEpochMs) {
    static SourceState of(String sourceId, long seq, double cpuPct) {
        return new SourceState(sourceId, seq, cpuPct, System.currentTimeMillis());
    }
}
