// examples/ex03-vehicle-state-cache/VehicleState.java —— 车辆实时状态快照(不可变 record)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
record VehicleState(String vin, long seq, double socPct, long updatedEpochMs) {
    static VehicleState of(String vin, long seq, double socPct) {
        return new VehicleState(vin, seq, socPct, System.currentTimeMillis());
    }
}
