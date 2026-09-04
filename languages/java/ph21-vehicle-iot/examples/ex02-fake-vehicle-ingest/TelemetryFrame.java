// examples/ex02-fake-vehicle-ingest/TelemetryFrame.java —— 解析后的遥测帧(不可变 record)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
record TelemetryFrame(String vin, long seq, double socPct, double kmh, double motorTempC) {
    /** 生产链路常把帧的文本/字节形态与业务形态分开：本 record 是后者。 */
    static TelemetryFrame of(String vin, long seq, double soc, double kmh, double temp) {
        return new TelemetryFrame(vin, seq, soc, kmh, temp);
    }
}
