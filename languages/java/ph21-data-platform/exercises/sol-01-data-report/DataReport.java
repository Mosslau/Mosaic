// exercises/sol-01-source-report/DataReport.java —— 数据源上报数据(record)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-sol *.java
record DataReport(String sourceId, long seq, double cpuPct, double latencyMs, double diskTempC) {
    boolean idValid() {
        return sourceId != null && sourceId.startsWith("LSV") && sourceId.length() == 10;
    }
    boolean rangeValid() {
        return cpuPct >= 0.0 && cpuPct <= 100.0
                && latencyMs >= 0.0 && latencyMs <= 220.0
                && diskTempC >= -40.0 && diskTempC <= 150.0;
    }
}
