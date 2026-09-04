// exercises/sol-04-telemetry-consumer/TelemetryMsg.java —— 遥测消息(record，分区键 = VIN)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-sol *.java
record TelemetryMsg(String vin, long seq, double socPct) {
    /** 幂等键：同车同 seq 全平台只处理一次。 */
    String idempotencyKey() { return vin + "#" + seq; }
}
