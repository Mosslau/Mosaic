// exercises/sol-01-vehicle-report/VehicleReport.java —— 车辆上报数据(record)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-sol *.java
record VehicleReport(String vin, long seq, double socPct, double kmh, double motorTempC) {
    boolean vinValid() {
        return vin != null && vin.startsWith("LSV") && vin.length() == 10;
    }
    boolean rangeValid() {
        return socPct >= 0.0 && socPct <= 100.0
                && kmh >= 0.0 && kmh <= 220.0
                && motorTempC >= -40.0 && motorTempC <= 150.0;
    }
}
